#!/bin/bash
# Ablation script for EoH Framework
# cd into project root
cd "$(dirname "$0")"

# Activate your env here if needed
# source ~/miniconda3/bin/activate eoh

run_ablation() {
    local EXP_NAME=$1
    export ABLATION_M1=$2
    export ABLATION_M2=$3
    export ABLATION_M3=$4
    export ABLATION_M4=$5
    export ABLATION_M5=$6

    echo "========================================================="
    echo "▶ Starting Experiment: $EXP_NAME"
    echo "▶ M1(Math):$ABLATION_M1 M2(AST):$ABLATION_M2 M3(Pareto):$ABLATION_M3 M4(Pass@K):$ABLATION_M4 M5(Island):$ABLATION_M5"
    echo "========================================================="
    
    export EXP_OUTPUT_PATH="./results_ablation/results_${EXP_NAME}"
    
    # We pass PYTHONPATH directly
    PYTHONPATH="./eoh/src" ~/miniconda3/envs/eoh/bin/python examples/salem_spencer/runEoH.py > "./results_ablation/log_${EXP_NAME}.txt" 2>&1

    echo "✅ Finished Experiment: $EXP_NAME"
}

# Ensure results folder exists
mkdir -p ./results_ablation

# --- Phase 1: Add-One-In (Single feature vs Baseline) ---
# Run 2 at a time taking up 4 CPU threads based on your setup.
run_ablation "Vanilla"      0  0  0  0  0 &
run_ablation "Only_M1"      1  0  0  0  0 &
wait

run_ablation "Only_M2"      0  1  0  0  0 &
run_ablation "Only_M3"      0  0  1  0  0 &
wait

run_ablation "Only_M4"      0  0  0  1  0 &
run_ablation "Only_M5"      0  0  0  0  1 &
wait

# --- Phase 2: Leave-One-Out (Remove one from Ultimate) ---
run_ablation "Ultimate"     1  1  1  1  1 &
run_ablation "No_M1"        0  1  1  1  1 &
wait

run_ablation "No_M2"        1  0  1  1  1 &
run_ablation "No_M3"        1  1  0  1  1 &
wait

run_ablation "No_M4"        1  1  1  0  1 &
run_ablation "No_M5"        1  1  1  1  0 &
wait

echo "🎉 All ablation experiments finished successfully."