"""
CSIFormer Dual-Branch Fusion Network: Hybrid Raw CSI + Doppler DFS Fusion.

Supports three fusion paradigms:
1. Feature Concatenation ("concat")
2. Cross-Attention Fusion ("cross_attention")
3. Gated Feature Fusion ("gated")

Includes contrastive projection head for Subject-Invariant Pretraining (Phase 13.3).
"""

import math
from typing import Dict, Any, Optional, Tuple, Union
import torch
import torch.nn as nn
import torch.nn.functional as F

from app.models.csiformernet import (
    SinusoidalPositionalEncoding,
    CNNSpatialFeatureExtractor,
    TemporalAttention
)


class CSIDualBranchFusionNet(nn.Module):
    """
    Dual-Branch CSIFormer Architecture for Raw CSI + Doppler DFS Fusion.

    Branch A (Raw): Encodes high-resolution amplitude & multipath floor (critical for Fall Recall & HAR).
    Branch B (Doppler): Encodes Doppler Frequency Shift spectrograms (subject-invariant kinematics).
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
        doppler_bins: int = 56,
        seq_len: int = 50,
        num_classes: int = 12,
        embed_dim: int = 128,
        nhead: int = 8,
        num_layers: int = 3,
        dim_feedforward: int = 512,
        dropout: float = 0.1,
        fusion_mode: str = "gated",  # "concat", "cross_attention", "gated"
        proj_dim: int = 128
    ):
        super().__init__()
        assert fusion_mode in ("concat", "cross_attention", "gated"), (
            f"Invalid fusion_mode '{fusion_mode}'. Must be 'concat', 'cross_attention', or 'gated'."
        )

        self.num_subcarriers = num_subcarriers
        self.doppler_bins = doppler_bins
        self.seq_len = seq_len
        self.num_classes = num_classes
        self.embed_dim = embed_dim
        self.fusion_mode = fusion_mode

        # =====================================================================
        # Branch A: Raw CSI Encoder
        # =====================================================================
        self.raw_cnn = CNNSpatialFeatureExtractor(
            in_subcarriers=num_subcarriers,
            embed_dim=embed_dim,
            dropout=dropout
        )
        self.raw_spatial_proj = nn.Linear(embed_dim, embed_dim)
        self.raw_spatial_norm = nn.LayerNorm(embed_dim)
        self.raw_pos_encoder = SinusoidalPositionalEncoding(d_model=embed_dim, max_len=seq_len * 2)

        raw_encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True
        )
        self.raw_transformer = nn.TransformerEncoder(raw_encoder_layer, num_layers=num_layers)
        self.raw_norm = nn.LayerNorm(embed_dim)
        self.raw_temporal_pool = TemporalAttention(d_model=embed_dim, hidden_dim=embed_dim // 2)

        # =====================================================================
        # Branch B: Doppler DFS Encoder
        # =====================================================================
        self.dopp_cnn = CNNSpatialFeatureExtractor(
            in_subcarriers=doppler_bins,
            embed_dim=embed_dim,
            dropout=dropout
        )
        self.dopp_spatial_proj = nn.Linear(embed_dim, embed_dim)
        self.dopp_spatial_norm = nn.LayerNorm(embed_dim)
        self.dopp_pos_encoder = SinusoidalPositionalEncoding(d_model=embed_dim, max_len=seq_len * 2)

        dopp_encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True
        )
        self.dopp_transformer = nn.TransformerEncoder(dopp_encoder_layer, num_layers=num_layers)
        self.dopp_norm = nn.LayerNorm(embed_dim)
        self.dopp_temporal_pool = TemporalAttention(d_model=embed_dim, hidden_dim=embed_dim // 2)

        # =====================================================================
        # Fusion Modules
        # =====================================================================
        if fusion_mode == "concat":
            # Direct feature concatenation followed by MLP projection
            self.fusion_mlp = nn.Sequential(
                nn.Linear(embed_dim * 2, embed_dim),
                nn.LayerNorm(embed_dim),
                nn.GELU(),
                nn.Dropout(dropout)
            )
        elif fusion_mode == "cross_attention":
            # Multi-Head Cross Attention: Query = Raw tokens, Key/Value = Doppler tokens
            self.cross_attn = nn.MultiheadAttention(
                embed_dim=embed_dim,
                num_heads=nhead,
                dropout=dropout,
                batch_first=True
            )
            self.cross_norm = nn.LayerNorm(embed_dim)
            self.cross_temporal_pool = TemporalAttention(d_model=embed_dim, hidden_dim=embed_dim // 2)
            self.fusion_mlp = nn.Sequential(
                nn.Linear(embed_dim * 2, embed_dim),
                nn.LayerNorm(embed_dim),
                nn.GELU()
            )
        elif fusion_mode == "gated":
            # Learnable gating vector: g = sigmoid(W_g [raw; doppler] + b_g)
            self.gate_dense = nn.Sequential(
                nn.Linear(embed_dim * 2, embed_dim),
                nn.LayerNorm(embed_dim),
                nn.GELU(),
                nn.Linear(embed_dim, embed_dim),
                nn.Sigmoid()
            )
            self.gate_norm = nn.LayerNorm(embed_dim)

        # =====================================================================
        # Multi-Task Classification Heads
        # =====================================================================
        self.activity_head = nn.Sequential(
            nn.Linear(embed_dim, 64),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(64, num_classes)
        )

        self.presence_head = nn.Sequential(
            nn.Linear(embed_dim, 32),
            nn.GELU(),
            nn.Linear(32, 1)
        )

        self.motion_head = nn.Sequential(
            nn.Linear(embed_dim, 32),
            nn.GELU(),
            nn.Linear(32, 1)
        )

        # =====================================================================
        # Contrastive Projection Head (Phase 13.3)
        # =====================================================================
        self.proj_head = nn.Sequential(
            nn.Linear(embed_dim, embed_dim),
            nn.ReLU(),
            nn.Linear(embed_dim, proj_dim)
        )

    def forward_branch_raw(self, x_raw: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        if len(x_raw.shape) == 2:
            x_raw = x_raw.unsqueeze(0)
        cnn_feat = self.raw_cnn(x_raw)
        proj = self.raw_spatial_norm(self.raw_spatial_proj(cnn_feat))
        enc = self.raw_pos_encoder(proj)
        tokens = self.raw_norm(self.raw_transformer(enc))
        context, _ = self.raw_temporal_pool(tokens)
        return tokens, context

    def forward_branch_dopp(self, x_dopp: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        if len(x_dopp.shape) == 2:
            x_dopp = x_dopp.unsqueeze(0)
        cnn_feat = self.dopp_cnn(x_dopp)
        proj = self.dopp_spatial_norm(self.dopp_spatial_proj(cnn_feat))
        enc = self.dopp_pos_encoder(proj)
        tokens = self.dopp_norm(self.dopp_transformer(enc))
        context, _ = self.dopp_temporal_pool(tokens)
        return tokens, context

    def forward(
        self,
        x_raw: torch.Tensor,
        x_dopp: Optional[torch.Tensor] = None,
        return_dict: bool = True
    ) -> Union[Dict[str, torch.Tensor], Tuple[torch.Tensor, torch.Tensor, torch.Tensor]]:
        """
        Forward pass for Dual-Branch CSIFormer.

        :param x_raw: Raw CSI tensor [Batch, TimeSteps, Subcarriers]
        :param x_dopp: Doppler DFS tensor [Batch, TimeSteps, DopplerBins]
                       If None, duplicates x_raw or raises if shapes mismatch.
        """
        if x_dopp is None:
            # Fallback for single-tensor pipelines
            x_dopp = x_raw

        # Branch Encodings
        raw_tokens, raw_context = self.forward_branch_raw(x_raw)
        dopp_tokens, dopp_context = self.forward_branch_dopp(x_dopp)

        # Fusion
        if self.fusion_mode == "concat":
            cat_feat = torch.cat([raw_context, dopp_context], dim=-1)
            fused_context = self.fusion_mlp(cat_feat)
            gate_weights = None

        elif self.fusion_mode == "cross_attention":
            # Attend Doppler kinematics onto Raw amplitude temporal sequence
            attn_out, _ = self.cross_attn(query=raw_tokens, key=dopp_tokens, value=dopp_tokens)
            attended_tokens = self.cross_norm(raw_tokens + attn_out)
            attn_context, _ = self.cross_temporal_pool(attended_tokens)
            fused_context = self.fusion_mlp(torch.cat([raw_context, attn_context], dim=-1))
            gate_weights = None

        elif self.fusion_mode == "gated":
            cat_feat = torch.cat([raw_context, dopp_context], dim=-1)
            gate = self.gate_dense(cat_feat)  # [Batch, embed_dim] in (0, 1)
            fused_context = self.gate_norm(gate * raw_context + (1.0 - gate) * dopp_context)
            gate_weights = gate

        # Multi-task heads
        activity_logits = self.activity_head(fused_context)
        presence_logits = self.presence_head(fused_context)
        motion_logits = self.motion_head(fused_context)
        presence_prob = torch.sigmoid(presence_logits)
        motion_prob = torch.sigmoid(motion_logits)

        # Contrastive normalized projection
        proj_features = F.normalize(self.proj_head(fused_context), dim=-1)

        if return_dict:
            res = {
                "activity_logits": activity_logits,
                "activity_class": torch.argmax(activity_logits, dim=-1),
                "presence_logits": presence_logits,
                "presence_probability": presence_prob,
                "motion_logits": motion_logits,
                "motion_probability": motion_prob,
                "latent_features": fused_context,
                "projected_features": proj_features,
                "raw_context": raw_context,
                "dopp_context": dopp_context,
            }
            if gate_weights is not None:
                res["gate_weights"] = gate_weights
            return res

        return activity_logits, presence_prob, motion_prob
