"""
Phase 58.1 Offline Metric Verification and Calculation Check.
"""
import json

# Data extracted from task-1258.log JSON output
total_raw_lines = 333
candidate_records = 318
valid_records_parsed = 316
target_records = 107
filtered_non_target_records = 209
parse_errors = 2
firmware_sequence_gaps = 2
target_sequence_gaps = 206

target_duration_s = 30.0
actual_duration_s = 30.0044
start_wall = 1792568172.2631137
stop_wall = 1792568202.268363
wall_duration_s = stop_wall - start_wall

# 1. Duration check
print(f"Wall duration: {wall_duration_s:.6f} s")
print(f"Reported actual duration (perf_counter): {actual_duration_s:.4f} s")

# 2. Rate recalculations
target_rate_hz = target_records / actual_duration_s
agg_rate_hz = valid_records_parsed / actual_duration_s
print(f"Target rate: {target_rate_hz:.6f} Hz (Reported: 3.566 Hz)")
print(f"Aggregate rate: {agg_rate_hz:.6f} Hz (Reported: 10.532 Hz)")

# 3. Parse success fraction
parse_success_fraction = valid_records_parsed / candidate_records
print(f"Candidate parse success fraction: {parse_success_fraction:.6f} ({parse_success_fraction*100:.3f}%)")

# 4. Count reconciliations
print(f"Candidates = Valid + Errors: {valid_records_parsed} + {parse_errors} = {valid_records_parsed + parse_errors} == {candidate_records}: {valid_records_parsed + parse_errors == candidate_records}")
print(f"Valid = Target + NonTarget: {target_records} + {filtered_non_target_records} = {target_records + filtered_non_target_records} == {valid_records_parsed}: {target_records + filtered_non_target_records == valid_records_parsed}")
print(f"Non-candidate lines: {total_raw_lines} - {candidate_records} = {total_raw_lines - candidate_records}")

# 5. Temporal sufficiency calculation (50-frame window)
est_time_50_frames_avg = 50.0 / target_rate_hz
mean_interval_reported_s = 0.27763
est_time_50_frames_interval = 49 * mean_interval_reported_s
print(f"Estimated time to accumulate 50 target frames (via avg rate): {est_time_50_frames_avg:.2f} s")
print(f"Estimated span of 50 target frames (via mean interval 49 * dt): {est_time_50_frames_interval:.2f} s")

# 6. Historical 50-frame window span for comparison
hist_rate_hz = 37.0
est_hist_time_50_frames = 50.0 / hist_rate_hz
print(f"Historical 50-frame span at 37 Hz: {est_hist_time_50_frames:.2f} s")
