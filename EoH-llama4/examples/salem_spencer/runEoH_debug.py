# examples/salem_spencer/runEoH_debug.py
import os, time, functools
from eoh import eoh
from eoh.utils.getParas import Paras
import eoh.problems.optimization.salem_spencer.run as ss_run

# 指定輸出資料夾，確保子程序、平行處理時路徑一致
OUTDIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(OUTDIR, exist_ok=True)
os.environ["EOH_OUTDIR"] = OUTDIR

# --- 猴子補丁：攔截 evaluate()，只要被呼叫就寫一行到 invoke.log ---
orig_evaluate = ss_run.SALEMSPENCER.evaluate

@functools.wraps(orig_evaluate)
def debug_evaluate(self, code_string):
    try:
        with open(os.path.join(OUTDIR, "invoke.log"), "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} evaluate() called, code_len={len(code_string) if code_string is not None else 'None'}\n")
    except Exception:
        pass
    return orig_evaluate(self, code_string)

ss_run.SALEMSPENCER.evaluate = debug_evaluate
# ------------------------------------------------------------------

# 參數
paras = Paras()
paras.set_paras(
    method="eoh",
    problem="salem_spencer",
    llm_use_local=True,
    llm_local_url="http://127.0.0.1:8001/v1/completions",  # 你的 LiteLLM Proxy
    llm_local_model="gemini-2.5-pro",                           # 你的 model 名
    ec_pop_size=2,
    ec_n_pop=1,
    exp_n_proc=1,       # 先單核，debug 比較單純
    exp_debug_mode=True # 打開 EoH 自己的 debug 訊息（若有）
)
paras.problem_args = {"n": 82}

evolution = eoh.EVOL(paras)
evolution.run()

print(f"\n[DEBUG] 看看 {OUTDIR} /invoke.log、/fitness.log、/errors.log、/candidates/ 有沒有新東西")
