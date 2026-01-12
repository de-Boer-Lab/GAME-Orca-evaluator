'''Calculate and save the final evaluation metrics.'''

# NOTE: Every evaluator will do this slightly differently depending on how the data is presented

import os
import sys
import json
import pandas as pd
import numpy as np
import itertools
from datetime import datetime, timezone

from config import EVALUATOR_NAME, EVALUATOR_INPUT_PATH

def _save_df_to_csv(df, filepath):
    """
    Appends a DataFrame to a CSV file, adding a header if the file is new.
    """
    if df.empty:
        print(f"No metrics to save for {os.path.basename(filepath)}. Skipping.")
        return
    
    try:
        file_exists = os.path.isfile(filepath)
        df.to_csv(filepath, mode='a', sep='\t', header=(not file_exists), index=False)
        print(f"DEBUG: Metrics file '{filepath}' exists: {file_exists}")
        if file_exists:
            print(f"Appended metrics to {filepath}")
        else:
            print(f"Created new metrics file {filepath}")
    except IOError as e:
        print(f"\nError: Could not save metrics to {filepath}. {e}", file=sys.stderr)


import numpy as np
import torch, warnings
from datetime import datetime, timezone
import pandas as pd
from scipy.stats import pearsonr

ORCA_PATH = '/orca/'
sys.path.append(ORCA_PATH)
import orca_predict
orca_predict.load_resources(models=['1M'], use_cuda=torch.cuda.is_available())
from orca_predict import h1esc_1m, target_h1esc_1m


def calculate_and_save_metrics(predictions_data, output_dir, recv_fmt):
    print("----- Starting Orca Evaluation (Pearson r) -----")
    is_msgpack_numpy = recv_fmt not in ["application/msgpack", "application/json"]
    if is_msgpack_numpy:
        print("Format = msgpack-numpy (using extra NaN safety checks)")
    else:
        print("Format = json/msgpack (standard processing)")

    # Load input to get seq coords & count
    with open(EVALUATOR_INPUT_PATH, 'r') as f:
        input_data = json.load(f)
    seq_dict = input_data["sequence_coordinates"]   # {key: [chr, coord]}
    seq_len = 1000000

    correlations = {}
    model = h1esc_1m

    for key, (chr, coord) in seq_dict.items():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            target = target_h1esc_1m.get_feature_data(chr, coord, coord + seq_len)[None, :, :]

            level = 4
            start = 0
            target_r = np.nanmean(
                np.nanmean(
                    np.reshape(
                        target[:, start:start+250*level, start:start+250*level],
                        (target.shape[0], 250, level, 250, level)
                    ),
                    axis=4
                ),
                axis=2
            )
            level = 1
            target_np = np.log(
                (target_r + model.epss[level]) /
                (model.normmats[level] + model.epss[level])
            )[0, :, :]

        valid = np.isfinite(target_np)
        pred_arr = np.array(predictions_data['prediction_tasks'][0]['predictions'][key])
        # ---- only msgpack-numpy needs extra NaN check ----
        if is_msgpack_numpy and np.all(np.isnan(target_np)):
            print(f"Skipping {key}: target is all NaNs")
            continue

        corr = pearsonr(pred_arr[valid], target_np[valid])[0]
        correlations[key] = corr
        print(f"{key} correlation: {corr}")

    mean_correlation = sum(correlations.values()) / len(correlations)
    predictor_name = predictions_data.get("predictor_name", "Unknown").replace(" ", "_")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S.%f")
    output_filename = f"{EVALUATOR_NAME}_from_{predictor_name}.csv"

    df = pd.DataFrame([{
        "Evaluator_Name": EVALUATOR_NAME,
        "Description": "EVALUATOR_NAME",
        "Predictor_Name": predictor_name,
        "Time_Stamp": timestamp,
        "Metric": "pearson_r",
        "Value": str(mean_correlation),
        "Prediction_task(s)_data": [
            {k: v for k, v in predictions_data["prediction_tasks"][0].items() if k != "predictions"}
        ],
    }])

    out_path = os.path.join(output_dir, output_filename)
    df.to_csv(out_path, sep="\t", index=False)
    print(f"Saved metrics to {out_path}")