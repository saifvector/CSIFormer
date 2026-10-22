import sys
import json
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))
sys.path.insert(0, str(BASE_DIR))

from app.services.split_generator import ParticipantIndependentSplitGenerator
from app.services.physics_csi_preprocessor import PhysicsCSIPreprocessor

CLASS_MAP = {
    "push_pull": 0,
    "clap": 1,
    "walk": 2,
    "static": 3,
    "sit": 4
}
CLASS_NAMES = ["push_pull", "clap", "walk", "static", "sit"]

def load_data():
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
    
    # Store windows: (session_id, activity, window_array)
    windows_dict = {"train": [], "val": [], "test": []}
    
    for s in sessions:
        sp = s["split"]
        if sp not in windows_dict:
            continue
        act = s["activity_label"]
        if act not in CLASS_MAP:
            continue
        sid = s["session_id"]
        
        p = data_dir / s["json_file"]
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        frames = data["frames"]
        amps = np.array([f["amplitudes"] for f in frames], dtype=np.float32)
        n_wins = len(frames) // 50
        
        for w in range(n_wins):
            raw_win = amps[w*50 : (w+1)*50]  # [50, 56]
            windows_dict[sp].append({
                "session_id": sid,
                "activity": act,
                "y": CLASS_MAP[act],
                "raw_win": raw_win
            })
            
    print(f"Loaded: train={len(windows_dict['train'])}, val={len(windows_dict['val'])}, test={len(windows_dict['test'])}")
    return windows_dict, preprocessor

def extract_features(win_list, preprocessor, feature_type="summary"):
    X = []
    y = []
    sessions = []
    
    for item in win_list:
        raw_win = item["raw_win"]  # [50, 56]
        
        if feature_type == "flattened_normalized":
            # Per-window column-wise normalization matching LivePipelineService
            m = raw_win.mean(axis=0, keepdims=True)
            s = raw_win.std(axis=0, keepdims=True) + 1e-6
            norm = (raw_win - m) / s
            feat = norm.flatten()  # 2800 features
            
        elif feature_type == "summary":
            # Domain summary features across physical subcarriers
            # Extract 5 physical subcarrier channels: [0, 13, 27, 41, 55]
            sc_idx = [0, 13, 27, 41, 55]
            sub = raw_win[:, sc_idx]  # [50, 5]
            
            # Temporal stats per physical subcarrier
            mean_sc = sub.mean(axis=0)  # 5
            std_sc = sub.std(axis=0)    # 5
            ptp_sc = np.ptp(sub, axis=0) # 5
            diff_energy_sc = np.mean(np.diff(sub, axis=0)**2, axis=0) # 5
            
            # Global summary stats across all 56 subcarriers
            global_mean_var = np.mean(np.var(raw_win, axis=0))
            global_max_var = np.max(np.var(raw_win, axis=0))
            global_diff_energy = np.mean(np.diff(raw_win, axis=0)**2)
            
            # Doppler summary stats from STFT
            dopp = preprocessor.compute_doppler_spectrogram(raw_win)  # [50, 56]
            dopp_mean = np.mean(dopp)
            dopp_var = np.var(dopp)
            dopp_max = np.max(dopp)
            
            feat = np.concatenate([
                mean_sc, std_sc, ptp_sc, diff_energy_sc,
                [global_mean_var, global_max_var, global_diff_energy],
                [dopp_mean, dopp_var, dopp_max]
            ])  # 5*4 + 3 + 3 = 26 features
            
        X.append(feat)
        y.append(item["y"])
        sessions.append(item["session_id"])
        
    return np.array(X, dtype=np.float32), np.array(y, dtype=int), sessions

def evaluate_model(clf, X_train, y_train, X_val, y_val, model_name=""):
    clf.fit(X_train, y_train)
    
    train_preds = clf.predict(X_train)
    val_preds = clf.predict(X_val)
    
    train_acc = accuracy_score(y_train, train_preds)
    val_acc = accuracy_score(y_val, val_preds)
    
    _, _, train_f1, _ = precision_recall_fscore_support(y_train, train_preds, average="macro", zero_division=0)
    _, _, val_f1, _ = precision_recall_fscore_support(y_val, val_preds, average="macro", zero_division=0)
    
    cm_val = confusion_matrix(y_val, val_preds, labels=[0, 1, 2, 3, 4])
    
    print(f"\n=== Model: {model_name} ===")
    print(f"  Train Acc: {train_acc*100:.1f}%, Train Macro-F1: {train_f1:.4f}")
    print(f"  Val Acc:   {val_acc*100:.1f}%, Val Macro-F1:   {val_f1:.4f}")
    print("  Val Confusion Matrix (labels 0..4 = push_pull, clap, walk, static, sit):")
    for i, row in enumerate(cm_val):
        print(f"    {CLASS_NAMES[i]:10s}: {row.tolist()}")
        
    p, r, f1, sup = precision_recall_fscore_support(y_val, val_preds, labels=[0, 1, 2, 3, 4], zero_division=0)
    print("  Val Per-Class Metrics:")
    for i in range(5):
        print(f"    {CLASS_NAMES[i]:10s} (N={sup[i]}): Prec={p[i]:.2f}, Rec={r[i]:.2f}, F1={f1[i]:.2f}")
        
    return {
        "model": model_name,
        "train_acc": train_acc,
        "train_f1": train_f1,
        "val_acc": val_acc,
        "val_f1": val_f1,
        "val_cm": cm_val.tolist(),
        "val_per_class": {
            CLASS_NAMES[i]: {"prec": float(p[i]), "rec": float(r[i]), "f1": float(f1[i]), "support": int(sup[i])}
            for i in range(5)
        }
    }

def main():
    windows_dict, preprocessor = load_data()
    
    # Candidate 1: Majority Baseline
    train_y = np.array([w["y"] for w in windows_dict["train"]])
    val_y = np.array([w["y"] for w in windows_dict["val"]])
    maj_class = int(np.bincount(train_y).argmax())
    maj_train_preds = np.full_like(train_y, maj_class)
    maj_val_preds = np.full_like(val_y, maj_class)
    print(f"\n=== Majority Class Baseline (Class {maj_class} = {CLASS_NAMES[maj_class]}) ===")
    print(f"  Train Acc: {accuracy_score(train_y, maj_train_preds)*100:.1f}%")
    print(f"  Val Acc:   {accuracy_score(val_y, maj_val_preds)*100:.1f}%")
    _, _, maj_val_f1, _ = precision_recall_fscore_support(val_y, maj_val_preds, average="macro", zero_division=0)
    print(f"  Val Macro-F1: {maj_val_f1:.4f}")

    # Evaluate feature sets
    for feat_type in ["summary", "flattened_normalized"]:
        print(f"\n=======================================================")
        print(f"FEATURE TYPE: {feat_type}")
        print(f"=======================================================")
        
        X_train, y_train, _ = extract_features(windows_dict["train"], preprocessor, feature_type=feat_type)
        X_val, y_val, _ = extract_features(windows_dict["val"], preprocessor, feature_type=feat_type)
        
        # Fit scaler ONLY on training data
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_val_scaled = scaler.transform(X_val)
        
        print(f"X_train shape: {X_train.shape}, X_val shape: {X_val.shape}")
        
        # Candidate 2: Regularized Linear Classifier (Logistic Regression)
        logreg = LogisticRegression(C=0.1, max_iter=1000, random_state=42)
        evaluate_model(logreg, X_train_scaled, y_train, X_val_scaled, y_val, f"LogisticRegression(C=0.1) [{feat_type}]")
        
        logreg_c1 = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
        evaluate_model(logreg_c1, X_train_scaled, y_train, X_val_scaled, y_val, f"LogisticRegression(C=1.0) [{feat_type}]")

        # Candidate 3: Random Forest
        rf = RandomForestClassifier(n_estimators=100, max_depth=4, min_samples_split=4, random_state=42)
        evaluate_model(rf, X_train, y_train, X_val, y_val, f"RandomForest(n=100, max_depth=4) [{feat_type}]")
        
        # Candidate 3b: Support Vector Machine (RBF)
        svm_rbf = SVC(kernel="rbf", C=1.0, random_state=42)
        evaluate_model(svm_rbf, X_train_scaled, y_train, X_val_scaled, y_val, f"SVC(kernel=rbf, C=1.0) [{feat_type}]")

        # Candidate 3c: Support Vector Machine (Linear)
        svm_lin = SVC(kernel="linear", C=0.1, random_state=42)
        evaluate_model(svm_lin, X_train_scaled, y_train, X_val_scaled, y_val, f"SVC(kernel=linear, C=0.1) [{feat_type}]")

if __name__ == "__main__":
    main()
