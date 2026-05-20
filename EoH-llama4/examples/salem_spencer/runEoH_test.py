# examples/salem_spencer/runEoH.py
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
            ec_pop_size=4,
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
            ec_m = 2, # number of parents
            ec_pop_size=2,
            ec_n_pop=2,
            exp_n_proc=2,
            exp_debug_mode=False,
            eva_timeout = 1800,
            exp_output_path="./results-ec_pop_size_32_n_pop_256-flash-dynamic-reasoning-debug-n-1094-probability-rank-m-8-hardcode-prompt-gptoss-120b-no-szker's-pass@10",
            # selection="tournament",
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
