import torch
import torch.nn as nn
import torch.nn.functional as F


class FocalBCELoss(nn.Module):
    """
    Cost-sensitive Focal Loss for multi-label classification.

    Combines:
    1. BCEWithLogitsLoss as base
    2. Cost matrix weighting (different penalty per class)
    3. Focal loss (focus on hard examples)
    """

    def __init__(self, cost_weights: torch.Tensor, gamma: float = 2.0, reduction: str = "mean"):
        """
        Args:
            cost_weights: tensor [num_classes] with clinical cost weights
                         SOR (emergency) has highest weight (e.g., 10)
                         POZ (primary care) has lowest weight (e.g., 1)
            gamma: focal loss exponent (higher = focus more on hard examples)
            reduction: 'mean' or 'sum'
        """
        super().__init__()
        self.register_buffer("cost_weights", cost_weights)
        self.gamma = gamma
        self.reduction = reduction

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Args:
            logits: [batch_size, num_classes] raw model outputs
            targets: [batch_size, num_classes] binary labels {0, 1}

        Returns:
            scalar loss
        """

        probs = torch.sigmoid(logits)

        bce = F.binary_cross_entropy_with_logits(
            logits, targets, reduction="none"
        )

        p_t = probs * targets + (1 - probs) * (1 - targets)

        focal_weight = (1 - p_t) ** self.gamma

        weighted_loss = bce * focal_weight * self.cost_weights.unsqueeze(0)

        if self.reduction == "mean":
            return weighted_loss.mean()
        elif self.reduction == "sum":
            return weighted_loss.sum()
        else:
            return weighted_loss


class ECELoss(nn.Module):
    """Expected Calibration Error — measures how well predicted probabilities match actual frequencies."""

    def __init__(self, n_bins: int = 15):
        super().__init__()
        self.n_bins = n_bins

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Args:
            logits: [batch_size, num_classes]
            targets: [batch_size, num_classes] binary labels

        Returns:
            ECE scalar (lower is better, target < 0.012)
        """
        probs = torch.sigmoid(logits)

        ece = torch.tensor(0.0, device=logits.device)
        count = 0

        for class_idx in range(logits.shape[1]):
            class_probs = probs[:, class_idx]
            class_targets = targets[:, class_idx]

            bin_boundaries = torch.linspace(0, 1, self.n_bins + 1, device=logits.device)

            for bin_start, bin_end in zip(bin_boundaries[:-1], bin_boundaries[1:]):
                mask = (class_probs >= bin_start) & (class_probs < bin_end)

                if mask.sum() == 0:
                    continue

                avg_confidence = class_probs[mask].mean()
                accuracy = class_targets[mask].float().mean()

                ece += torch.abs(avg_confidence - accuracy) * (mask.float().mean())
                count += 1

        if count > 0:
            ece = ece / count

        return ece
