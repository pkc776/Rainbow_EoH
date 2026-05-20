# examples/salem_spencer/runEoH.py
import os
import faulthandler
import signal

# Enable traceback dump on SIGUSR1
faulthandler.register(signal.SIGUSR1)
print(f"DEBUG: Faulthandler enabled. PID={os.getpid()}. Run 'kill -30 {os.getpid()}' to dump traceback.")

from eoh.eoh import EVOL
from eoh.utils.getParas import Paras

USE_LOCAL = False  # True -> LiteLLM/OpenAI-compatible proxy; False -> call remote API directly

def main():
    paras = Paras()

    if USE_LOCAL:
        # LiteLLM (or any OpenAI-compatible) server you already tested at :8001
        paras.set_paras(
            method="eoh",
            problem="salem_spencer",
            llm_use_local=True,
            llm_local_url="http://127.0.0.1:8001/v1/completions",  # ← 改這行：用 completions
            ec_n_pop=4,
            exp_n_proc=4,
            exp_debug_mode=True,
        )
    else:
        # Call remote Gemini (OpenAI-compatible) endpoint directly
        paras.set_paras(
            method="eoh",
            problem="salem_spencer",
            llm_api_endpoint="https://inner-medusa.genai.nchc.org.tw/v1",
            llm_api_key="sk-LlcHGASv3jH1-fboFpSNTg",
            # llm_model="Llama-4-Maverick-17B-128E-Instruct-FP8",
            llm_model="gpt-oss-120b",
            ec_m = 8, # number of parents
            ec_pop_size=8,  # Reduce for faster ablation
            ec_n_pop=64,    # Reduce for faster ablation
            exp_n_proc=2,
            exp_debug_mode=False,
            eva_timeout = 3600,
            exp_use_seed=False,
            exp_seed_path="./seeds/seeds.json",
            exp_output_path=os.environ.get("EXP_OUTPUT_PATH", "./results-ablation-default"),
            # selection="tournament",
            
            # --- Continue Evolution Settings ---

            exp_use_continue=False,
            exp_continue_id=2, # Continue from generation 2
            exp_continue_path="./results-ec_pop_size_32_n_pop_256-flash-dynamic-reasoning-debug-n-1094-probability-rank-m-8-hardcode-prompt-gptoss-120b-recursive-ternary-seed/results/pops/population_generation_2.json",
        )

    # choose n here
    paras.problem_args = {"n": 1094}

    evo = EVOL(paras)
    evo.run()

if __name__ == "__main__":
    import sys, eoh as eohpkg, eoh.problems.optimization.salem_spencer.run as R
    print("[whoami] python =", sys.executable, flush=True)
    print("[whoami] eoh pkg =", eohpkg.__file__, flush=True)
    print("[whoami] SS run.py =", R.__file__, flush=True)
    main()
