"""
CSIFormerNet: Spatial-Temporal Vision Transformer for Wi-Fi Channel State Information.

Architecture:
Input [Batch, TimeSteps, Subcarriers]
  ↓
CNN Feature Extractor (1D Residual Spatial-Frequency Convolution)
  ↓
Spatial Encoder (Linear Projection + Sinusoidal Positional Encoding)
  ↓
Transformer Encoder (Pre-LN Multi-Head Self-Attention)
  ↓
Temporal Attention Pooling (Learnable Attention Score Aggregation)
  ↓
Multi-Task Classification Heads:
  - activity_logits [Batch, num_classes]
  - presence_probability [Batch, 1]
  - motion_probability [Batch, 1]

Supports variable sequence lengths, batch training, and Automatic Mixed Precision (AMP).
"""

import math
from typing import Dict, Any, Optional, Tuple, Union
import torch
import torch.nn as nn
import torch.nn.functional as F


class SinusoidalPositionalEncoding(nn.Module):
    """Sinusoidal Positional Encoding supporting arbitrary sequence lengths."""

    def __init__(self, d_model: int, max_len: int = 500):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))

        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x shape: [Batch, Sequence_Len, d_model]
        seq_len = x.size(1)
        if seq_len > self.pe.size(1):
            # Dynamically extend buffer if needed
            device = x.device
            pe_ext = torch.zeros(seq_len, self.pe.size(-1), device=device)
            pos = torch.arange(0, seq_len, dtype=torch.float, device=device).unsqueeze(1)
            div = torch.exp(torch.arange(0, self.pe.size(-1), 2, device=device).float() * (-math.log(10000.0) / self.pe.size(-1)))
            pe_ext[:, 0::2] = torch.sin(pos * div)
            pe_ext[:, 1::2] = torch.cos(pos * div)
            return x + pe_ext.unsqueeze(0)
        return x + self.pe[:, :seq_len]


class CNNSpatialFeatureExtractor(nn.Module):
    """
    Multi-Scale 1D Residual CNN Feature Extractor.
    Extracts local spectral-frequency correlation across subcarrier channels.
    """

    def __init__(self, in_subcarriers: int = 56, embed_dim: int = 128, dropout: float = 0.1):
        super().__init__()
        self.conv1 = nn.Conv1d(
            in_channels=in_subcarriers,
            out_channels=embed_dim,
            kernel_size=3,
            padding=1,
            bias=False
        )
        self.bn1 = nn.BatchNorm1d(embed_dim)
        self.act1 = nn.GELU()

        self.conv2 = nn.Conv1d(
            in_channels=embed_dim,
            out_channels=embed_dim,
            kernel_size=3,
            padding=1,
            bias=False
        )
        self.bn2 = nn.BatchNorm1d(embed_dim)
        self.act2 = nn.GELU()

        self.drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Input x: [Batch, TimeSteps, Subcarriers]
        # Transpose to [Batch, Subcarriers, TimeSteps] for 1D convolution along time
        x_t = x.transpose(1, 2)
        out = self.act1(self.bn1(self.conv1(x_t)))
        out = self.drop(self.act2(self.bn2(self.conv2(out))))
        # Transpose back: [Batch, TimeSteps, embed_dim]
        return out.transpose(1, 2)


class TemporalAttention(nn.Module):
    """
    Learnable Attention-Based Pooling over Sequence Tokens.
    Computes importance scores alpha_t and performs weighted summation.
    """

    def __init__(self, d_model: int, hidden_dim: int = 64):
        super().__init__()
        self.attn_net = nn.Sequential(
            nn.Linear(d_model, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, 1, bias=False)
        )

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        # Input x: [Batch, TimeSteps, d_model]
        # Attention scores: [Batch, TimeSteps, 1]
        scores = self.attn_net(x)
        weights = F.softmax(scores, dim=1)
        # Context vector: [Batch, d_model]
        context = torch.sum(x * weights, dim=1)
        return context, weights.squeeze(-1)


class CSIFormerNet(nn.Module):
    """
    CSIFormer Deep Learning Neural Network.
    Combines Spatial CNN, Transformer Temporal Attention, and Multi-Task Heads.
    """

    DEFAULT_CLASSES = [
        "Push&Pull",
        "Sweep",
        "Clap",
        "Slide",
        "Draw-O",
        "Draw-Zigzag",
        "box",
        "circle",
        "clean",
        "fall",
        "run",
        "walk"
    ]

    def __init__(
        self,
        num_subcarriers: int = 56,
        seq_len: int = 50,
        num_classes: int = 12,
        embed_dim: int = 128,
        nhead: int = 8,
        num_layers: int = 3,
        dim_feedforward: int = 512,
        dropout: float = 0.1
    ):
        """
        Initialize CSIFormerNet.

        :param num_subcarriers: Number of OFDM subcarrier channels (56 for HT20, 114 for HT40).
        :param seq_len: Nominal sequence length (supports variable lengths at runtime).
        :param num_classes: Number of human activity / gesture classes.
        :param embed_dim: Latent representation dimensionality.
        :param nhead: Number of multi-head attention heads.
        :param num_layers: Number of Transformer encoder layers.
        :param dim_feedforward: Feedforward network dimension.
        :param dropout: Dropout probability.
        """
        super().__init__()
        self.num_subcarriers = num_subcarriers
        self.seq_len = seq_len
        self.num_classes = num_classes
        self.embed_dim = embed_dim

        # 1. Spatial CNN Feature Extractor
        self.cnn_extractor = CNNSpatialFeatureExtractor(
            in_subcarriers=num_subcarriers,
            embed_dim=embed_dim,
            dropout=dropout
        )

        # 2. Spatial Encoder Projection & Positional Encoding
        self.spatial_proj = nn.Linear(embed_dim, embed_dim)
        self.spatial_norm = nn.LayerNorm(embed_dim)
        self.pos_encoder = SinusoidalPositionalEncoding(d_model=embed_dim, max_len=seq_len * 2)

        # 3. Transformer Encoder (Pre-LN for Mixed Precision stability)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.transformer_norm = nn.LayerNorm(embed_dim)

        # 4. Temporal Attention Pooling
        self.temporal_attention = TemporalAttention(d_model=embed_dim, hidden_dim=embed_dim // 2)

        # 5. Multi-Task Classification Heads
        # Head 1: Activity Classification (12 classes)
        self.activity_head = nn.Sequential(
            nn.Linear(embed_dim, 64),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(64, num_classes)
        )

        # Head 2: Presence Head (Outputs unscaled logits for BCEWithLogitsLoss)
        self.presence_head = nn.Sequential(
            nn.Linear(embed_dim, 32),
            nn.GELU(),
            nn.Linear(32, 1)
        )

        # Head 3: Motion Head (Outputs unscaled logits for BCEWithLogitsLoss)
        self.motion_head = nn.Sequential(
            nn.Linear(embed_dim, 32),
            nn.GELU(),
            nn.Linear(32, 1)
        )

    def forward(
        self,
        x: torch.Tensor,
        return_dict: bool = True
    ) -> Union[Dict[str, torch.Tensor], Tuple[torch.Tensor, torch.Tensor, torch.Tensor]]:
        """
        Forward pass of CSIFormerNet.

        :param x: CSI input tensor of shape [Batch, TimeSteps, Subcarriers].
        :param return_dict: If True, return dictionary of outputs; else tuple.
        :return: Dict containing activity_logits, presence_probability, motion_probability.
        """
        # Ensure input shape [Batch, TimeSteps, Subcarriers]
        if len(x.shape) == 2:
            x = x.unsqueeze(0)

        # Step 1: 1D CNN Spatial-Spectral Feature Extraction
        cnn_features = self.cnn_extractor(x)  # [Batch, TimeSteps, embed_dim]

        # Step 2: Spatial Linear Projection + Positional Encoding
        projected = self.spatial_norm(self.spatial_proj(cnn_features))
        encoded = self.pos_encoder(projected)

        # Step 3: Transformer Encoder
        trans_out = self.transformer(encoded)
        trans_out = self.transformer_norm(trans_out)

        # Step 4: Temporal Attention Pooling
        context, attn_weights = self.temporal_attention(trans_out)  # [Batch, embed_dim]

        # Step 5: Multi-Task Heads
        activity_logits = self.activity_head(context)           # [Batch, num_classes]
        presence_logits = self.presence_head(context)           # [Batch, 1]
        motion_logits = self.motion_head(context)               # [Batch, 1]
        presence_prob = torch.sigmoid(presence_logits)          # [Batch, 1]
        motion_prob = torch.sigmoid(motion_logits)              # [Batch, 1]

        if return_dict:
            return {
                "activity_logits": activity_logits,
                "activity_class": torch.argmax(activity_logits, dim=-1),
                "presence_logits": presence_logits,
                "presence_probability": presence_prob,
                "motion_logits": motion_logits,
                "motion_probability": motion_prob,
                "attention_weights": attn_weights,
                "latent_features": context
            }

        return activity_logits, presence_prob, motion_prob
