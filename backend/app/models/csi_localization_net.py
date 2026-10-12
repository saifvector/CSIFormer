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
    """1D CNN Feature Extractor for Wi-Fi Subcarrier Features."""
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

class CSILocalizationNet(nn.Module):
    """
    CSILocalizationNet PyTorch Deep Learning Model.
    Predicts 3D spatial target coordinates (X, Y, Z) and localization confidence score
    from sliding window Wi-Fi CSI subcarrier matrices [Batch, Time_Steps=50, Subcarriers=64].
    
    Room Bounding Limits:
    X: [0.0m .. 10.0m] (Centered 3D: [-5.0m .. +5.0m])
    Y: [0.0m .. 8.0m]  (Centered 3D: [-4.0m .. +4.0m])
    Z: [0.0m .. 3.5m]  (Centered 3D: [0.0m .. 3.5m])
    """
    def __init__(self, num_subcarriers: int = 64, seq_len: int = 50, embed_dim: int = 128, nhead: int = 8, num_layers: int = 2):
        super(CSILocalizationNet, self).__init__()
        self.seq_len = seq_len
        self.num_subcarriers = num_subcarriers

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

        # Regression Head predicting: (X, Y, Z, Confidence)
        self.regressor = nn.Sequential(
            nn.Linear(embed_dim, 64),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(64, 4)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Input shape: [Batch, 50, 64]
        spatial_feats = self.spatial_cnn(x)
        pos_feats = self.pos_encoder(spatial_feats)
        trans_out = self.transformer(pos_feats)
        pooled = trans_out.mean(dim=1)
        
        out = self.regressor(pooled) # [Batch, 4] -> (X, Y, Z, Conf_Logit)
        
        # Scale outputs to valid room bounds:
        x_coord = torch.sigmoid(out[:, 0:1]) * 10.0 # [0..10m]
        y_coord = torch.sigmoid(out[:, 1:2]) * 8.0  # [0..8m]
        z_coord = torch.sigmoid(out[:, 2:3]) * 3.5  # [0..3.5m]
        conf = torch.sigmoid(out[:, 3:4])           # [0..1]
        
        return torch.cat([x_coord, y_coord, z_coord, conf], dim=-1)
