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
        # x shape: [Batch, Sequence_Len, d_model]
        return x + self.pe[:, :x.size(1)]

class CNNSpatialExtractor(nn.Module):
    """
    1D/2D CNN Feature Extractor for Wi-Fi Subcarriers.
    Extracts spatial-spectral signal characteristics from 64 OFDM subcarriers.
    """
    def __init__(self, in_subcarriers: int = 64, embed_dim: int = 128):
        super(CNNSpatialExtractor, self).__init__()
        self.conv1 = nn.Conv1d(in_channels=in_subcarriers, out_channels=128, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm1d(128)
        self.act1 = nn.GELU()
        
        self.conv2 = nn.Conv1d(in_channels=128, out_channels=embed_dim, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm1d(embed_dim)
        self.act2 = nn.GELU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Input x shape: [Batch, Time_Steps=50, Subcarriers=64]
        # Transpose for Conv1d: [Batch, Subcarriers=64, Time_Steps=50]
        x = x.transpose(1, 2)
        x = self.act1(self.bn1(self.conv1(x)))
        x = self.act2(self.bn2(self.conv2(x)))
        # Transpose back: [Batch, Time_Steps=50, embed_dim=128]
        return x.transpose(1, 2)

class CSIFormerNet(nn.Module):
    """
    CSIFormer Deep Learning Architecture.
    Combines CNN Spatial Subcarrier Feature Extractor and Temporal Transformer Encoder
    for 8-Class Wi-Fi Channel State Information Human Activity Recognition.
    
    Supported Activity Classes (8):
    0: Empty Room
    1: Standing
    2: Sitting
    3: Walking
    4: Running
    5: Falling
    6: Lying Down
    7: Multiple Persons
    """
    CLASSES = [
        "Empty Room",
        "Standing",
        "Sitting",
        "Walking",
        "Running",
        "Falling",
        "Lying Down",
        "Multiple Persons"
    ]

    def __init__(self, num_subcarriers: int = 64, seq_len: int = 50, num_classes: int = 8, embed_dim: int = 128, nhead: int = 8, num_layers: int = 2):
        super(CSIFormerNet, self).__init__()
        self.seq_len = seq_len
        self.num_subcarriers = num_subcarriers
        self.num_classes = num_classes

        # 1. Spatial CNN Extractor
        self.spatial_cnn = CNNSpatialExtractor(in_subcarriers=num_subcarriers, embed_dim=embed_dim)
        
        # 2. Positional Encoding
        self.pos_encoder = PositionalEncoding(d_model=embed_dim, max_len=seq_len + 10)
        
        # 3. Temporal Transformer Encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=nhead,
            dim_feedforward=256,
            dropout=0.1,
            activation='gelu',
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # 4. Classification Head
        self.classifier = nn.Sequential(
            nn.Linear(embed_dim, 64),
            nn.GELU(),
            nn.Dropout(0.2),
            nn.Linear(64, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Input tensor x shape: [Batch, Time_Steps=50, Subcarriers=64]
        spatial_features = self.spatial_cnn(x) # [Batch, 50, 128]
        pos_features = self.pos_encoder(spatial_features) # [Batch, 50, 128]
        
        # Temporal Self-Attention Transformer
        trans_out = self.transformer(pos_features) # [Batch, 50, 128]
        
        # Mean pooling across sequence dimension
        pooled = trans_out.mean(dim=1) # [Batch, 128]
        
        # Output Logits
        logits = self.classifier(pooled) # [Batch, 8]
        return logits

    def predict_probs(self, x: torch.Tensor) -> torch.Tensor:
        """Returns softmax probability distribution over 8 activity classes."""
        logits = self.forward(x)
        return F.softmax(logits, dim=-1)
