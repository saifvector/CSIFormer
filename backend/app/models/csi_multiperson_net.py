import math
import torch
import torch.nn as nn
import torch.nn.functional as F

class PositionalEncoding(nn.Module):
    """Sinusoidal Positional Encoding for CSI Temporal Sequence Modeling."""
    def __init__(self, d_model: int, max_len: int = 100):
        super(PositionalEncoding, self).__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:, :x.size(1)]

class CNNSpatialExtractor(nn.Module):
    """1D CNN Feature Extractor for Wi-Fi Subcarriers."""
    def __init__(self, in_subcarriers: int = 64, embed_dim: int = 128):
        super(CNNSpatialExtractor, self).__init__()
        self.conv1 = nn.Conv1d(in_channels=in_subcarriers, out_channels=128, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm1d(128)
        self.act1 = nn.GELU()
        
        self.conv2 = nn.Conv1d(in_channels=128, out_channels=embed_dim, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm1d(embed_dim)
        self.act2 = nn.GELU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x.transpose(1, 2)
        x = self.act1(self.bn1(self.conv1(x)))
        x = self.act2(self.bn2(self.conv2(x)))
        return x.transpose(1, 2)

class CSIMultiPersonNet(nn.Module):
    """
    CSIMultiPersonNet PyTorch Deep Learning Model.
    Predicts:
    1. Person Count Classification (0, 1, 2, 3, 4+ targets)
    2. Multi-Target 3D Coordinates [Batch, Max_Targets=4, 4] -> (X, Y, Z, Confidence)
    from sliding window Wi-Fi CSI subcarrier matrices [Batch, Time_Steps=50, Subcarriers=64].
    """
    def __init__(self, num_subcarriers: int = 64, seq_len: int = 50, max_targets: int = 4, embed_dim: int = 128, nhead: int = 8, num_layers: int = 2):
        super(CSIMultiPersonNet, self).__init__()
        self.seq_len = seq_len
        self.num_subcarriers = num_subcarriers
        self.max_targets = max_targets

        self.spatial_cnn = CNNSpatialExtractor(in_subcarriers=num_subcarriers, embed_dim=embed_dim)
        self.pos_encoder = PositionalEncoding(d_model=embed_dim, max_len=seq_len + 10)
        
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=nhead,
            dim_feedforward=256,
            dropout=0.1,
            activation='gelu',
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # Head 1: Person Count Classification (0..4 targets -> 5 logits)
        self.count_head = nn.Sequential(
            nn.Linear(embed_dim, 64),
            nn.GELU(),
            nn.Linear(64, 5)
        )

        # Head 2: Multi-Target Coordinate Regression [Max_Targets=4, 4]
        self.coord_head = nn.Sequential(
            nn.Linear(embed_dim, 128),
            nn.GELU(),
            nn.Linear(128, max_targets * 4)
        )

    def forward(self, x: torch.Tensor):
        # Input shape: [Batch, 50, 64]
        spatial_feats = self.spatial_cnn(x)
        pos_feats = self.pos_encoder(spatial_feats)
        trans_out = self.transformer(pos_feats)
        pooled = trans_out.mean(dim=1)
        
        count_logits = self.count_head(pooled) # [Batch, 5]
        
        coord_raw = self.coord_head(pooled).view(-1, self.max_targets, 4) # [Batch, 4, 4]
        
        # Scale target coordinates to room bounds
        x_coords = torch.sigmoid(coord_raw[:, :, 0:1]) * 10.0
        y_coords = torch.sigmoid(coord_raw[:, :, 1:2]) * 8.0
        z_coords = torch.sigmoid(coord_raw[:, :, 2:3]) * 3.5
        confs = torch.sigmoid(coord_raw[:, :, 3:4])
        
        coords_scaled = torch.cat([x_coords, y_coords, z_coords, confs], dim=-1)
        return count_logits, coords_scaled
