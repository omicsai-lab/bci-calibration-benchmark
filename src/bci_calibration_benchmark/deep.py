"""Optional fixed-protocol Braindecode EEGNet estimator.

This adapter intentionally uses a fixed epoch count and training-only standardization.
It is not enabled in the primary v0.1 configurations.
"""

from __future__ import annotations

import random
from typing import Any

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.utils.validation import check_is_fitted


class BraindecodeEEGNetClassifier(BaseEstimator, ClassifierMixin):
    def __init__(
        self,
        n_channels: int,
        n_times: int,
        sfreq: float,
        epochs: int = 100,
        batch_size: int = 64,
        learning_rate: float = 1e-3,
        weight_decay: float = 0.0,
        random_state: int = 0,
        device: str = "cpu",
    ):
        self.n_channels = n_channels
        self.n_times = n_times
        self.sfreq = sfreq
        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.random_state = random_state
        self.device = device

    @staticmethod
    def _imports() -> tuple[Any, Any]:
        try:
            import torch
            from braindecode.models import EEGNet
        except ImportError as error:
            raise RuntimeError(
                "The optional deep dependencies are required: pip install -e '.[deep]'"
            ) from error
        return torch, EEGNet

    def _standardize_fit(self, X: np.ndarray) -> np.ndarray:
        self.channel_mean_ = X.mean(axis=(0, 2), keepdims=True)
        self.channel_std_ = X.std(axis=(0, 2), keepdims=True)
        self.channel_std_ = np.where(self.channel_std_ < 1e-7, 1.0, self.channel_std_)
        return (X - self.channel_mean_) / self.channel_std_

    def _standardize_transform(self, X: np.ndarray) -> np.ndarray:
        check_is_fitted(self, ("channel_mean_", "channel_std_"))
        return (X - self.channel_mean_) / self.channel_std_

    def fit(self, X: np.ndarray, y: np.ndarray) -> BraindecodeEEGNetClassifier:
        torch, EEGNet = self._imports()
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y, dtype=np.int64)
        if X.ndim != 3 or X.shape[1:] != (self.n_channels, self.n_times):
            raise ValueError(
                f"Expected X shape (*, {self.n_channels}, {self.n_times}), got {X.shape}"
            )
        if set(np.unique(y).tolist()) != {0, 1}:
            raise ValueError("EEGNet training requires both classes")
        if self.epochs < 1 or self.batch_size < 2 or self.learning_rate <= 0:
            raise ValueError("Invalid EEGNet training hyperparameters")

        random.seed(self.random_state)
        np.random.seed(self.random_state)
        torch.manual_seed(self.random_state)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(self.random_state)
        try:
            torch.use_deterministic_algorithms(True, warn_only=True)
        except TypeError:
            torch.use_deterministic_algorithms(True)

        device = torch.device(self.device)
        X_standardized = self._standardize_fit(X).astype(np.float32, copy=False)
        tensor_x = torch.from_numpy(X_standardized)
        tensor_y = torch.from_numpy(y)
        generator = torch.Generator()
        generator.manual_seed(self.random_state)
        dataset = torch.utils.data.TensorDataset(tensor_x, tensor_y)
        batch_size = min(self.batch_size, len(dataset))
        if batch_size < 2:
            raise ValueError("EEGNet requires at least two training epochs")
        loader = torch.utils.data.DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=True,
            generator=generator,
            drop_last=(len(dataset) > batch_size and len(dataset) % batch_size == 1),
        )

        model = EEGNet(
            n_chans=self.n_channels,
            n_outputs=2,
            n_times=self.n_times,
            sfreq=float(self.sfreq),
        ).to(device)
        optimizer = torch.optim.AdamW(
            model.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay
        )
        criterion = torch.nn.CrossEntropyLoss()
        self.loss_history_ = []
        model.train()
        for _ in range(self.epochs):
            total_loss = 0.0
            total_examples = 0
            for batch_x, batch_y in loader:
                batch_x = batch_x.to(device)
                batch_y = batch_y.to(device)
                optimizer.zero_grad(set_to_none=True)
                logits = model(batch_x)
                loss = criterion(logits, batch_y)
                loss.backward()
                optimizer.step()
                total_loss += float(loss.detach().cpu()) * len(batch_y)
                total_examples += len(batch_y)
            self.loss_history_.append(total_loss / max(total_examples, 1))
        self.model_ = model.eval()
        self.device_ = str(device)
        self.classes_ = np.asarray([0, 1], dtype=int)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        check_is_fitted(self, ("model_", "classes_"))
        torch, _ = self._imports()
        X = np.asarray(X, dtype=np.float32)
        if X.ndim != 3 or X.shape[1:] != (self.n_channels, self.n_times):
            raise ValueError("EEGNet prediction shape mismatch")
        X_standardized = self._standardize_transform(X).astype(np.float32, copy=False)
        device = torch.device(self.device_)
        probabilities: list[np.ndarray] = []
        self.model_.eval()
        with torch.no_grad():
            for start in range(0, len(X_standardized), self.batch_size):
                batch = torch.from_numpy(X_standardized[start : start + self.batch_size]).to(device)
                logits = self.model_(batch)
                probabilities.append(torch.softmax(logits, dim=1).cpu().numpy())
        return np.concatenate(probabilities, axis=0)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.argmax(self.predict_proba(X), axis=1)
