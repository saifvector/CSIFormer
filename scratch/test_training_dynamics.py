import sys
import json
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))
sys.path.insert(0, str(BASE_DIR))

from app.services.split_generator import ParticipantIndependentSplitGenerator
from app.services.physics_csi_preprocessor import PhysicsCSIPreprocessor
from app.models.csiformer_dual_branch import CSIDualBranchFusionNet

CLASS_TO_IDX = {
    "push_pull": 0,
    "clap": 1,
    "walk": 2,
    "static": 3,
    "sit": 4
}

def extract_windows():
    manifest_path = BASE_DIR / "data" / "real_csi_dataset" / "dataset_manifest.json"
    data_dir = BASE_DIR / "data" / "real_csi_dataset"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    gen = ParticipantIndependentSplitGenerator(manifest)
    split = gen.generate_strict_cross_room_split()
    sessions = split["sessions"]
    
    preprocessor = PhysicsCSIPreprocessor(
        carrier_freq=2.442e9,
        source_rate_hz=30.0,
        target_timesteps=50,
        target_channels=56,
        stft_window=32,
        stft_noverlap=24,
        stft_nfft=64
    )
    
    datasets = {"train": ([], [], []), "val": ([], [], []), "test": ([], [], [])}
    
    for s in sessions:
        split_name = s["split"]
        if split_name not in datasets:
            continue
        act = s["activity_label"]
        if act not in CLASS_TO_IDX:
            continue
        y = CLASS_TO_IDX[act]
        
        p = data_dir / s["json_file"]
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        frames = data["frames"]
        amps = np.array([f["amplitudes"] for f in frames], dtype=np.float32)
        n_wins = len(frames) // 50
        
        for w in range(n_wins):
            raw_win = amps[w*50 : (w+1)*50]  # [50, 56]
            
            # Normalization matching LivePipelineService
            amp_mean = raw_win.mean(axis=0, keepdims=True)
            amp_std = raw_win.std(axis=0, keepdims=True) + 1e-6
            norm_raw = (raw_win - amp_mean) / amp_std
            
            # Doppler STFT matching LivePipelineService
            norm_dopp = preprocessor.compute_doppler_spectrogram(raw_win)
            
            datasets[split_name][0].append(norm_raw)
            datasets[split_name][1].append(norm_dopp)
            datasets[split_name][2].append(y)
            
    out = {}
    for k in datasets:
        x_raw = torch.tensor(np.array(datasets[k][0]), dtype=torch.float32)
        x_dopp = torch.tensor(np.array(datasets[k][1]), dtype=torch.float32)
        y = torch.tensor(np.array(datasets[k][2]), dtype=torch.long)
        out[k] = (x_raw, x_dopp, y)
        print(f"Loaded {k}: x_raw={x_raw.shape}, x_dopp={x_dopp.shape}, y={y.shape}")
        
    return out

def test_training():
    data = extract_windows()
    torch.manual_seed(42)
    np.random.seed(42)
    
    train_raw, train_dopp, train_y = data["train"]
    val_raw, val_dopp, val_y = data["val"]
    
    train_loader = DataLoader(
        TensorDataset(train_raw, train_dopp, train_y),
        batch_size=8,
        shuffle=True
    )
    
    model = CSIDualBranchFusionNet(
        num_subcarriers=56,
        doppler_bins=56,
        seq_len=50,
        num_classes=5,
        embed_dim=128,
        nhead=8,
        num_layers=3,
        dim_feedforward=512,
        dropout=0.3,
        fusion_mode="gated"
    )
    
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-2)
    
    print("\nStarting 20-epoch trial...")
    for epoch in range(1, 21):
        model.train()
        total_loss = 0.0
        correct = 0
        for b_raw, b_dopp, b_y in train_loader:
            optimizer.zero_grad()
            out = model(b_raw, b_dopp)
            loss = criterion(out["activity_logits"], b_y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(b_y)
            preds = out["activity_logits"].argmax(dim=-1)
            correct += (preds == b_y).sum().item()
            
        train_loss = total_loss / len(train_y)
        train_acc = correct / len(train_y)
        
        model.eval()
        with torch.no_grad():
            val_out = model(val_raw, val_dopp)
            val_loss = criterion(val_out["activity_logits"], val_y).item()
            val_preds = val_out["activity_logits"].argmax(dim=-1)
            val_acc = (val_preds == val_y).float().mean().item()
            
        if epoch % 2 == 0 or epoch == 1:
            print(f"Epoch {epoch:2d}: Train Loss={train_loss:.4f}, Train Acc={train_acc*100:.1f}%, Val Loss={val_loss:.4f}, Val Acc={val_acc*100:.1f}%")

if __name__ == "__main__":
    test_training()
