# # examples/salem_spencer/runEoH_sniff.py
# import os, time, json, threading, functools
# import requests

# from eoh import eoh
# from eoh.utils.getParas import Paras
# import eoh.problems.optimization.salem_spencer.run as ss_run


# import requests, json

# def _post_openai_compat(url: str, model: str, api_key: str | None, prompt: str) -> str:
#     headers = {"Content-Type": "application/json"}
#     if api_key:
#         headers["Authorization"] = f"Bearer {api_key}"

#     # 優先用 chat 端點；如果 url 不是 chat/completions 就走 completions
#     if "/chat/completions" in url:
#         payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}
#     else:
#         payload = {"model": model, "prompt": prompt}

#     r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
#     r.raise_for_status()
#     j = r.json()

#     # 優先解析 chat
#     try:
#         return (j["choices"][0]["message"]["content"] or "").strip()
#     except Exception:
#         pass
#     # 退回 completions
#     try:
#         return (j["choices"][0]["text"] or "").strip()
#     except Exception:
#         pass

#     raise RuntimeError(f"Unrecognized LLM response: {j}")

# # --- 統一輸出資料夾 ---
# OUTDIR = os.path.join(os.path.dirname(__file__), "results")
# os.makedirs(OUTDIR, exist_ok=True)
# os.environ["EOH_OUTDIR"] = OUTDIR

# # --- 1) 嗅探所有 HTTP 請求與回應（落在 results/llm_raw/） ---
# orig_request = requests.sessions.Session.request
# def sniff_request(self, method, url, *args, **kwargs):
#     resp = orig_request(self, method, url, *args, **kwargs)
#     try:
#         # 只存跟 LLM 相關的端點（你在用的 OpenAI-style /v1/chat/completions）
#         if any(k in url for k in ["/v1/chat/completions", "/v1/completions"]):
#             ts = time.strftime("%Y%m%d-%H%M%S")
#             tid = threading.get_ident()
#             dump_dir = os.path.join(OUTDIR, "llm_raw")
#             os.makedirs(dump_dir, exist_ok=True)

#             # 請求體
#             req_json = kwargs.get("json")
#             req_data = kwargs.get("data")
#             with open(os.path.join(dump_dir, f"req_{ts}_{tid}.json"), "w") as f:
#                 if req_json is not None:
#                     json.dump(req_json, f, ensure_ascii=False, indent=2)
#                 elif req_data is not None:
#                     f.write(req_data if isinstance(req_data, str) else str(req_data))
#                 else:
#                     f.write("<no-body>")

#             # 回應體
#             with open(os.path.join(dump_dir, f"resp_{ts}_{tid}.json"), "w") as f:
#                 f.write(resp.text)
#     except Exception:
#         pass
#     return resp

# requests.sessions.Session.request = sniff_request

# # --- 2) 猴子補丁 evaluate()：只要被叫就寫 invoke.log ---
# orig_evaluate = ss_run.SALEMSPENCER.evaluate
# @functools.wraps(orig_evaluate)
# def debug_evaluate(self, code_string):
#     try:
#         with open(os.path.join(OUTDIR, "invoke.log"), "a", encoding="utf-8") as f:
#             f.write(f"{time.strftime('%H:%M:%S')} evaluate() called, code_len={len(code_string) if code_string else 0}\n")
#     except Exception:
#         pass
#     return orig_evaluate(self, code_string)

# ss_run.SALEMSPENCER.evaluate = debug_evaluate

# # --- 3) 啟動 EoH（單核、最小族群，方便觀察） ---
# paras = Paras()
# paras.set_paras(
#     method="eoh",
#     problem="salem_spencer",
#     llm_use_local=True,                                   # 使用 LiteLLM Proxy
#     llm_local_url="http://127.0.0.1:11101/completions",
#     llm_local_model="gemini-2.5-pro",
#     ec_pop_size=1,
#     ec_n_pop=1,
#     exp_n_proc=1,        # 單核，stdout/落檔比較乾淨
#     exp_debug_mode=True
# )
# paras.problem_args = {"n": 365}

# evolution = eoh.EVOL(paras)
# evolution.run()

# print(f"\n[SNiff] DONE. Check under: {OUTDIR}")
# print(f"  - invoke.log (有就代表 evaluate() 被叫了)")
# print(f"  - llm_raw/*.json (看實際送出的 prompt 與回傳內容)")
# print(f"  - candidates/, fitness.log, errors.log（成功評分才會長東西）")
# examples/salem_spencer/runEoH_sniff.py
import os, time, json, threading, functools
import requests

from eoh import eoh
from eoh.utils.getParas import Paras
import eoh.problems.optimization.salem_spencer.run as ss_run

# --- 統一輸出資料夾 ---
OUTDIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(OUTDIR, exist_ok=True)
os.environ["EOH_OUTDIR"] = OUTDIR

# --- 1) 嗅探所有 HTTP 請求與回應（落在 results/llm_raw/） ---
orig_request = requests.sessions.Session.request

TARGET_SNiff = [
    "127.0.0.1:11101",           # 你的 Gemini 本機代理
    "/completions",              # 本機 /completions
    "/v1/completions",           # OpenAI-style
    "/v1/chat/completions",      # OpenAI-style chat
    "generativelanguage.googleapis.com",  # 直接打 Google 也記
]

def sniff_request(self, method, url, *args, **kwargs):
    resp = orig_request(self, method, url, *args, **kwargs)
    try:
        if any(t in url for t in TARGET_SNiff):
            ts = time.strftime("%Y%m%d-%H%M%S")
            tid = threading.get_ident()
            dump_dir = os.path.join(OUTDIR, "llm_raw")
            os.makedirs(dump_dir, exist_ok=True)

            # 解析請求 body
            req_json = kwargs.get("json")
            req_data = kwargs.get("data")
            req_body = req_json if req_json is not None else req_data
            # 嘗試抓出 prompt 片段，方便肉眼確認
            prompt_preview = ""
            try:
                obj = req_json if req_json is not None else json.loads(req_data) if isinstance(req_data, str) else None
                if isinstance(obj, dict):
                    if "prompt" in obj:
                        prompt_preview = obj["prompt"][:200]
                    elif "messages" in obj and obj["messages"]:
                        prompt_preview = str(obj["messages"][0])[:200]
            except Exception:
                pass

            # console 簡短印出
            print(f"\n[LLM-REQ] {method} {url}")
            if prompt_preview:
                print(f"[LLM-REQ] prompt[0..200]= {prompt_preview!r}")

            # 落檔：請求
            with open(os.path.join(dump_dir, f"req_{ts}_{tid}.json"), "w", encoding="utf-8") as f:
                if req_json is not None:
                    json.dump(req_json, f, ensure_ascii=False, indent=2)
                elif req_data is not None:
                    f.write(req_data if isinstance(req_data, str) else str(req_data))
                else:
                    f.write("<no-body>")

            # 落檔：回應
            with open(os.path.join(dump_dir, f"resp_{ts}_{tid}.json"), "w", encoding="utf-8") as f:
                f.write(resp.text)
    except Exception:
        pass
    return resp

requests.sessions.Session.request = sniff_request

# --- 2) 猴子補丁 evaluate()：只要被叫就寫 invoke.log ---
orig_evaluate = ss_run.SALEMSPENCER.evaluate
@functools.wraps(orig_evaluate)
def debug_evaluate(self, code_string):
    try:
        with open(os.path.join(OUTDIR, "invoke.log"), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} evaluate() called, code_len={len(code_string) if code_string else 0}\n")
    except Exception:
        pass
    return orig_evaluate(self, code_string)

ss_run.SALEMSPENCER.evaluate = debug_evaluate

# --- 3) 啟動 EoH（單核、最小族群，方便觀察） ---
paras = Paras()
paras.set_paras(
    method="eoh",
    problem="salem_spencer",
    llm_use_local=True,                                   # 一定要 True
    llm_local_url="http://127.0.0.1:11101/completions",   # ← 指向你的 gemini_server.py
    llm_local_model="gemini-2.5-flash",
    ec_pop_size=8, # each population 24 individuals
    ec_n_pop=96, # number of populations
    exp_n_proc=4, # 4 cores
    exp_debug_mode=False,
    eva_timeout = 600,
    exp_output_path="./results-ec_pop_size_8_n_pop_96-minimize-absolute-len-flash-dynamic-reasoning-debug-n-365"  # avoid overwriting previous results
)
paras.problem_args = {"n": 365}

# 額外：把 whoami 寫入 whoami.log，確認用的是哪個安裝來源
try:
    import sys, eoh as _eoh_pkg, eoh.problems.optimization.salem_spencer.run as _R
    with open(os.path.join(OUTDIR, "whoami.log"), "a", encoding="utf-8") as f:
        f.write(f"[whoami] python = {sys.executable}\n")
        f.write(f"[whoami] eoh pkg = {_eoh_pkg.__file__}\n")
        f.write(f"[whoami] SS run.py = {_R.__file__}\n")
except Exception:
    pass

evolution = eoh.EVOL(paras)
evolution.run()

print(f"\n[Sniff] DONE. Check under: {OUTDIR}")
print(f"  - invoke.log（evaluate() 有被叫到就會寫）")
print(f"  - llm_raw/*.json（看實際送出的 prompt 與回傳內容，現在會包含 11101/completions）")
print(f"  - candidates/, fitness.log, errors.log（成功評分才會長東西）")
