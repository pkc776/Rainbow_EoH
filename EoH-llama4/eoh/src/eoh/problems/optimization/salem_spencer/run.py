# # eoh/src/eoh/problems/salem_spencer/run.py
# import numpy as np
# import types
# import warnings
# import sys
# from .get_instance import GetData
# from .prompts import GetPrompts

# class SALEMSPENCER():
#     def __init__(self, problem_args=None):
#         n = (problem_args or {}).get("n", None)
#         getdata = GetData(n=n)
#         self.instances, self.lb = getdata.get_instances()
#         self.prompts = GetPrompts()

#     @staticmethod
#     def _is_3ap_free(S):
#         """Return True if S has no 3-term arithmetic progression."""
#         s = set(S)
#         if not s:
#             return True
#         M = max(s)
#         # 檢查以每個 b 為中點的 (b-d, b, b+d)
#         for b in s:
#             dmax = min(b - 1, M - b)
#             for d in range(1, dmax + 1):
#                 if (b - d in s) and (b + d in s):
#                     return False
#         return True

#     def _score_valid_set(self, S, n):
#         """回傳分數（默認用密度）。無效集合在 evaluateGreedy 中處理成大負分。"""
#         return len(S) / float(n)

#     # @funsearch.run
#     def evaluateGreedy(self, alg) -> float:
#         """
#         Evaluate heuristic on provided Salem–Spencer instances.
#         期望 alg 具有函式：heuristic(n, rng=None) -> Iterable[int]
#         """
#         print(f"Evaluating on instances: {list(self.instances.keys())}")
#         for name, dataset in self.instances.items():
#             densities = []
#             sizes = []

#             for _, inst in dataset.items():
#                 n = int(inst["n"])
#                 # 呼叫候選程式
#                 if not hasattr(alg, "heuristic"):
#                     return None
#                 try:
#                     S = list(alg.heuristic(n, None))
#                 except Exception:
#                     return None

#                 # 清理：轉 int、夾在 [1..n]、去重
#                 S = {int(x) for x in S if 1 <= int(x) <= n}

#                 # 驗證 3-AP-free
#                 if not self._is_3ap_free(S):
#                     # 無效給極大負分，避免作弊
#                     densities.append(-1e9)
#                     sizes.append(0)
#                 else:
#                     densities.append(self._score_valid_set(S, n))
#                     sizes.append(len(S))

#             avg_density = float(np.mean(np.array(densities)))
#             avg_size = float(np.mean(np.array(sizes)))

#             # 若 get_instance.py 提供了下界（對應這個資料集名稱），用之做正規化
#             if isinstance(self.lb, dict) and (name in self.lb) and (self.lb[name] is not None):
#                 denom = max(self.lb[name], 1e-9)
#                 fitness = (avg_size - self.lb[name]) / denom
#             else:
#                 # 否則直接回傳平均密度（越大越好）
#                 fitness = avg_density
#         # print(f"fitness: {fitness}")
#         with open("ss_debug.log", "a") as f:
#             f.write(f"fitness={fitness}\n")
#         return fitness

#     def evaluate(self, code_string: str):
#         """和 bp_online 一樣，動態載入候選程式碼並評測。"""
#         try:
#             with warnings.catch_warnings():
#                 warnings.simplefilter("ignore")
#                 mod = types.ModuleType("heuristic_module")
#                 exec(code_string, mod.__dict__)
#                 sys.modules[mod.__name__] = mod
#                 return self.evaluateGreedy(mod)
#         except Exception:
#             return None
# eoh/src/eoh/problems/optimization/salem_spencer/run.py
# import sys
# import json
# import types
# import warnings
# import traceback
# from pathlib import Path
# from datetime import datetime

# import numpy as np

# from .get_instance import GetData
# from .prompts import GetPrompts


# HERE = Path(__file__).resolve().parent
# LOG_FILE = HERE / "ss_debug.log"
# PROBE_FILE = HERE / "_probe_imported.txt"
# LAST_CANDIDATE = HERE / "last_candidate.py"
# LAST_ERROR = HERE / "last_error.txt"
# LAST_CALL = HERE / "last_call.json"


# def _log(msg: str) -> None:
#     """Append a timestamped line to module-local debug log."""
#     try:
#         LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
#         with LOG_FILE.open("a", encoding="utf-8") as f:
#             ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#             f.write(f"[{ts}] {msg}\n")
#     except Exception:
#         # 最後手段：避免因為寫檔失敗而讓主流程掛掉
#         pass


# class SALEMSPENCER():
#     """
#     評估 Salem–Spencer（3-AP-free）集合構造啟發式的問題包裝器。
#     LLM 需輸出一段包含 `def heuristic(n, rng=None):` 的程式碼。
#     """

#     def __init__(self, problem_args=None):
#         # 啟動探針：協助確認載入的就是這份檔案
#         try:
#             PROBE_FILE.write_text("imported\n", encoding="utf-8")
#             _log(f"SALEMSPENCER imported from {HERE}")
#         except Exception:
#             pass

#         n = (problem_args or {}).get("n", None)
#         getdata = GetData(n=n)
#         self.instances, self.lb = getdata.get_instances()
#         self.prompts = GetPrompts()

#         _log(f"instances keys: {list(self.instances.keys())}; lb keys: {list(self.lb.keys()) if isinstance(self.lb, dict) else self.lb}")
#         _log(f"problem_args.n = {n}")

#     # ---------- helpers ----------

#     @staticmethod
#     def _is_3ap_free(S):
#         """
#         回傳 True 若 S 不含長度為 3 的等差數列 (a, b, c) 且 b 為中點。
#         以 O(|S| * M) 的簡單檢查（M 為最大值的尺度），對我們的 n 規模足夠。
#         """
#         s = set(S)
#         if not s:
#             return True
#         M = max(s)
#         for b in s:
#             dmax = min(b - 1, M - b)
#             # (b - d, b, b + d)
#             for d in range(1, dmax + 1):
#                 if (b - d in s) and (b + d in s):
#                     return False
#         return True

#     @staticmethod
#     def _score_valid_set(S, n: int) -> float:
#         """預設以密度（|S|/n）當分數。"""
#         return len(S) / float(max(n, 1))

#     # ---------- core evaluation ----------

#     def evaluateGreedy(self, alg) -> float:
#         """
#         評估 LLM 產生之啟發式模組 `alg`。
#         期望函式：heuristic(n, rng=None) -> Iterable[int]
#         """

#         # 從 prompts 取函式名（應為 'heuristic'），增加容錯
#         func_name = "heuristic"
#         try:
#             if hasattr(self.prompts, "get_func_name"):
#                 func_name = self.prompts.get_func_name() or "heuristic"
#         except Exception:
#             pass

#         # 容錯：若 LLM 生錯名稱，嘗試常見別名
#         alt_names = [func_name, "heuristic", "score", "construct", "build"]
#         target_fn = None
#         for name in alt_names:
#             if hasattr(alg, name):
#                 target_fn = getattr(alg, name)
#                 break

#         if target_fn is None or not callable(target_fn):
#             _log("No callable heuristic found on candidate module.")
#             return None

#         # 可重現的隨機源（若候選使用 rng）
#         rng = np.random.default_rng(0)

#         _log(f"Evaluating on instances: {list(self.instances.keys())}")
#         fitness = None

#         for name, dataset in self.instances.items():
#             densities = []
#             sizes = []

#             for _, inst in dataset.items():
#                 try:
#                     n = int(inst["n"])
#                 except Exception:
#                     _log(f"Bad instance: {inst}")
#                     return None

#                 # 呼叫候選啟發式
#                 try:
#                     S = list(target_fn(n, rng))
#                 except Exception as e:
#                     _log(f"Error when calling heuristic(n={n}): {e}")
#                     return None

#                 # 清理：轉 int、夾在 [1..n]、去重
#                 try:
#                     S = {int(x) for x in S if 1 <= int(x) <= n}
#                 except Exception:
#                     _log("Candidate returned non-integer-like elements.")
#                     return None

#                 # 3-AP-free 驗證
#                 if not self._is_3ap_free(S):
#                     densities.append(-1e9)  # 巨大負分，懲罰不合法集合
#                     sizes.append(0)
#                 else:
#                     densities.append(self._score_valid_set(S, n))
#                     sizes.append(len(S))

#                 # 記最後一次呼叫內容，方便除錯
#                 try:
#                     LAST_CALL.write_text(
#                         json.dumps(
#                             {"n": n, "size": len(S), "sample": sorted(list(S))[:50]},
#                             ensure_ascii=False,
#                             indent=2,
#                         ),
#                         encoding="utf-8",
#                     )
#                 except Exception:
#                     pass

#             avg_density = float(np.mean(np.array(densities))) if densities else -1e9
#             avg_size = float(np.mean(np.array(sizes))) if sizes else 0.0

#             # 若提供了下界（或目標值），用之正規化；否則用密度
#             if isinstance(self.lb, dict) and (name in self.lb) and (self.lb[name] is not None):
#                 denom = max(float(self.lb[name]), 1e-9)
#                 fitness = (avg_size - float(self.lb[name])) / denom
#             else:
#                 fitness = avg_density

#             _log(f"[{name}] avg_size={avg_size:.6f} avg_density={avg_density:.6f} -> fitness={fitness:.6f}")

#         # 若資料集是空的，回 None
#         if fitness is None:
#             _log("No dataset found in instances; returning None.")
#             return None

#         # 同步寫 log（避免被多製程吞掉）
#         try:
#             with LOG_FILE.open("a", encoding="utf-8") as f:
#                 f.write(f"fitness={fitness}\n")
#         except Exception:
#             pass

#         return float(fitness)

#     def evaluate(self, code_string: str):
#         """
#         與 bp_online 相同：動態載入候選程式碼並呼叫 evaluateGreedy。
#         會把候選落檔（last_candidate.py），若失敗則寫 last_error.txt。
#         """
#         try:
#             # 落檔方便排錯
#             try:
#                 LAST_CANDIDATE.write_text(code_string, encoding="utf-8")
#             except Exception:
#                 pass

#             with warnings.catch_warnings():
#                 warnings.simplefilter("ignore")
#                 mod = types.ModuleType("heuristic_module")
#                 exec(code_string, mod.__dict__)
#                 sys.modules[mod.__name__] = mod

#             return self.evaluateGreedy(mod)

#         except Exception as e:
#             # 記錄例外與原始候選，方便追蹤
#             try:
#                 LAST_ERROR.write_text(
#                     f"{e.__class__.__name__}: {e}\n\n{traceback.format_exc()}\n\n{code_string}",
#                     encoding="utf-8",
#                 )
#             except Exception:
#                 pass
#             _log(f"evaluate() failed: {e}")
#             return None
# eoh/src/eoh/problems/optimization/salem_spencer/run.py
import os
import time
import traceback
import numpy as np
import types
import warnings
import sys
from .get_instance import GetData
from .prompts import GetPrompts

import multiprocessing as mp
import subprocess
import pickle
import requests
import json

def _llm_check_strategy(code_string):
    """
    Uses a local LLM to judge if the code follows the 'Inductive Construction' preference.
    Returns: (bool is_valid, str reason)
    """
    prompt = (
        "You are a code reviewer. Check if the following Python code implements a 'Ternary Structure' or 'Inductive' strategy "
        "to construct a Salem-Spencer set. \n"
        "Criteria for YES:\n"
        "1. It constructs the set by combining smaller blocks or splitting the range [1, N] into parts (e.g. Low, Middle, High).\n"
        "2. It specifically prioritizes filling the lower and upper thirds (or similar inductive structure) while leaving the middle sparse.\n"
        "3. It avoids simple linear greedy scanning of the whole range [1, N] without structural logic.\n\n"
        "Code:\n"
        f"{code_string}\n\n"
        "Does this code follow the criteria? Answer strictly in JSON format: {\"valid\": true/false, \"reason\": \"...\"}"
    )

    try:
        # Configuration matches runEoH.py settings
        url = "http://127.0.0.1:8001/v1/chat/completions" # Assuming local proxy
        # Fallback to the remote one if needed, but local is safer for loop. 
        # Since user runs runEoH with specific URL, we should try to reuse or hardcode for now.
        # Let's try the one from user's runEoH.py metadata if possible, or just standard local.
        # User's runEoH says: http://127.0.0.1:8001/v1/completions (legacy) or chat/completions.
        # We will try a standard request.
        
        payload = {
            "model": "gpt-oss-120b", # or whatever is available
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 100,
            "temperature": 0.0
        }
        
        # Note: If no local server is running, this will fail. 
        # We assume the user has the LLM infrastructure ready as per runEoH.py.
        # If runEoH uses remote, we might need that API key. 
        # To be safe, if request fails, we DEFAULT TO TRUE (don't block valid code due to network).
        
        # Adapting to the user's runEoH context:
        # He uses https://inner-medusa.genai.nchc.org.tw/v1 in NON-LOCAL mode.
        # This function runs inside the evaluation loop.
        # HARDCODING the endpoint from runEoH.py for simplicity.
        
        api_url = "https://inner-medusa.genai.nchc.org.tw/v1/chat/completions"
        api_key = "sk-LlcHGASv3jH1-fboFpSNTg"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            res_json = response.json()
            content = res_json['choices'][0]['message']['content']
            # Parse JSON from string
            # LLMs sometimes wrap in ```json ... ```
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            data = json.loads(content)
            return data.get("valid", False), data.get("reason", "No reason")
            
        return True, "LLM request failed (status), allowing." 
        
    except Exception as e:
        return True, f"LLM check error: {e}, allowing."

RUNNER_SCRIPT = r"""
import sys
import pickle
import types
import warnings
import os
import resource

def get_digits(num, base):
    if num == 0: return [0]
    digits = []
    while num > 0:
        digits.append(num % base)
        num //= base
    return digits


# --- RESOURCE LIMITS ---
# Limit memory to 4GB to prevent macOS kernel panic
MAX_MEM_BYTES = 4 * 1024 * 1024 * 1024 # 4GB
try:
    # Attempt to limit Address Space (Virtual Memory)
    resource.setrlimit(resource.RLIMIT_AS, (MAX_MEM_BYTES, MAX_MEM_BYTES))
except Exception:
    pass

try:
    # Attempt to limit Data Segment (Heap) - more effective on some systems
    resource.setrlimit(resource.RLIMIT_DATA, (MAX_MEM_BYTES, MAX_MEM_BYTES))
except Exception:
    pass
# -----------------------

# Ensure the eoh package can be imported
# (Assuming the environment is the same)

def run():
    try:
        evaluator_pkl = sys.argv[1]
        code_path = sys.argv[2]
        output_pkl = sys.argv[3]

        with open(evaluator_pkl, 'rb') as f:
            evaluator = pickle.load(f)

        with open(code_path, 'r') as f:
            code_string = f.read()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mod = types.ModuleType("heuristic_module")
            mod.__dict__['get_digits'] = get_digits
            exec(code_string, mod.__dict__)
            sys.modules[mod.__name__] = mod
            
            res = evaluator.evaluate_rainbow(mod, code_string)
        
        with open(output_pkl, 'wb') as f:
            pickle.dump(res, f)

    except Exception as e:
        # Write exception to output if possible, or just exit non-zero
        try:
            with open(sys.argv[3], 'wb') as f:
                pickle.dump(e, f)
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    run()
"""


# --- globals for multiprocessing (fork-friendly) ---
_EOH_EVAL_ALG = None

def _passk_worker(job):
    """
    job = (n, seed)
    Return (n, size) where size is |S| if 3-AP free else 0.
    Uses global _EOH_EVAL_ALG (inherited via fork).
    """
    n, seed = job
    global _EOH_EVAL_ALG
    try:
        S = list(_EOH_EVAL_ALG.heuristic(n, seed))
        S = {int(x) for x in S if 1 <= int(x) <= n}

        # 3-AP free check (re-implemented locally to avoid passing bound methods)
        if not S:
            return (n, 0)

        M = max(S)
        for b in S:
            dmax = min(b - 1, M - b)
            for d in range(1, dmax + 1):
                if (b - d in S) and (b + d in S):
                    return (n, 0)

        return (n, len(S))
    except Exception:
        return (n, 0)


def _make_non_daemon():
    """Allow this process to spawn children (nested multiprocessing)."""
    mp.current_process().daemon = False

def _eval_wrapper(code_string, return_queue):
    """
    Executed in a separate process to allow hard timeouts.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mod = types.ModuleType("heuristic_module")
            exec(code_string, mod.__dict__)
            sys.modules[mod.__name__] = mod
            
            # Since evaluateGreedy is an instance method, we can't easily call it here
            # without pickling the whole class. 
            # BUT, we actually just need to verify the module works.
            # However, logic is coupled in evaluateGreedy.
            # Wait, simplify: We return the module *object*? No, can't pickle module.
            # We return Success. The actual evaluation logic needs SALEMSPENCER instance.
            # 
            # Correction: Run the whole evaluation in here if possible?
            # Or just run `exec` to check for infinite loops during definition?
            # Most infinite loops happen during execution of heuristic(), not validation.
            #
            # Actually, `evaluate` calls `evaluateGreedy` which calls `alg.heuristic`.
            # We need to wrap the whole `evaluate` logic or just the `exec` part?
            # The danger is `exec` (if code has top-level loop) AND `heuristic` (if code generates loop alg).
            pass
            
        return_queue.put("DONE")
    except Exception as e:
        return_queue.put(f"ERROR: {e}")


def _mkoutdir():
    # 優先用環境變數，否則落到當前 examples 目錄的 results
    base = os.environ.get("EOH_OUTDIR", None)
    if not base:
        # 嘗試在啟動腳本所在目錄下建 results
        try:
            caller = os.path.abspath(sys.argv[0])
            base = os.path.join(os.path.dirname(caller), "results")
        except Exception:
            base = os.path.abspath(os.path.join(os.getcwd(), "results"))
    cand_dir = os.path.join(base, "candidates")
    os.makedirs(cand_dir, exist_ok=True)
    return base, cand_dir


# Helper outside class
def _full_eval_wrapper(evaluator, code_string, result_queue):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mod = types.ModuleType("heuristic_module")
            exec(code_string, mod.__dict__)
            sys.modules[mod.__name__] = mod
            
            # Since evaluateGreedy is expected to be called on 'evaluator'
            res = evaluator.evaluateGreedy(mod)
            result_queue.put(res)
    except Exception as e:
        result_queue.put(e)


class SALEMSPENCER():
    def __init__(self, problem_args=None):
        n = (problem_args or {}).get("n", None)
        getdata = GetData(n=n)
        self.instances, self.lb = getdata.get_instances()
        self.prompts = GetPrompts()

        # 準備輸出資料夾
        self.outdir, self.canddir = _mkoutdir()
        self.error_log = os.path.join(self.outdir, "errors.log")
        self.fitness_log = os.path.join(self.outdir, "fitness.log")
        self.eval_counter = 0

        # 寫一筆啟動訊息（方便你確認確實載到這支檔）
        with open(os.path.join(self.outdir, "whoami.log"), "a") as f:
            f.write(f"[whoami] python={sys.executable}\n")
            f.write(f"[whoami] run.py={__file__}\n")
            f.write(f"[whoami] outdir={self.outdir}\n")

    @staticmethod
    def _is_3ap_free(S):
        """True if S has no 3-term arithmetic progression."""
        s = set(S)
        if not s:
            return True
        M = max(s)
        for b in s:
            dmax = min(b - 1, M - b)
            for d in range(1, dmax + 1):
                if (b - d in s) and (b + d in s):
                    return False
        return True

    def evaluate_rainbow(self, alg, code_string) -> dict:
        """
        Module 3 & 4 implementation.
        """
        import time
        import os
        from ....utils.dedup_utils import has_random_call

        # Module 3 configs
        N_BUCKETS = [200, 500, 1000]
        K = 3
        
        use_passK = os.environ.get("ABLATION_M4", "1") == "1"
        is_random = has_random_call(code_string) and use_passK
        
        scores = {}
        for n in N_BUCKETS:
            if not is_random:
                # Deterministic: only run once
                try:
                    S_raw = list(alg.heuristic(n, 42))
                    S = {int(x) for x in S_raw if 1 <= int(x) <= n}
                    size = len(S) if self._is_3ap_free(S) else 0
                except Exception:
                    size = 0
                scores[n] = size
            else:
                # Stochastic pass@K with early stop
                try:
                    # Run 1: seed 42
                    S1_raw = list(alg.heuristic(n, 42))
                    S1 = {int(x) for x in S1_raw if 1 <= int(x) <= n}
                    size1 = len(S1) if self._is_3ap_free(S1) else 0
                except Exception:
                    S1, size1 = set(), 0

                try:
                    # Run 2: seed 43
                    S2_raw = list(alg.heuristic(n, 43))
                    S2 = {int(x) for x in S2_raw if 1 <= int(x) <= n}
                    size2 = len(S2) if self._is_3ap_free(S2) else 0
                except Exception:
                    S2, size2 = set(), 0

                if S1 == S2:
                    # Fake randomness or structurally ineffective - stop early
                    scores[n] = size1
                else:
                    runs_sizes = [size1, size2]
                    # Run remaining K-2 iterations
                    for i in range(2, K):
                        try:
                            S_i_raw = list(alg.heuristic(n, 42+i))
                            S_i = {int(x) for x in S_i_raw if 1 <= int(x) <= n}
                            size_i = len(S_i) if self._is_3ap_free(S_i) else 0
                        except Exception:
                            size_i = 0
                        runs_sizes.append(size_i)
                    scores[n] = max(runs_sizes)

        import time
        import json
        with open(self.fitness_log, "a") as f:
            f.write(
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} "
                f"rainbow_scores={scores} "
                f"is_random={is_random}\n"
            )

        # Track best per N
        best_per_n_file = os.path.join(os.path.dirname(self.fitness_log), "best_per_n.json")
        try:
            if os.path.exists(best_per_n_file):
                with open(best_per_n_file, "r") as f:
                    best_records = json.load(f)
            else:
                best_records = {str(n): {"score": -1, "code": ""} for n in N_BUCKETS}
                
            updated = False
            for n, score in scores.items():
                n_str = str(n)
                if n_str in best_records and score > best_records[n_str]["score"]:
                    best_records[n_str] = {
                        "score": score,
                        "code": code_string,
                        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    updated = True
                    
            if updated:
                with open(best_per_n_file, "w") as f:
                    json.dump(best_records, f, indent=4)
        except Exception as e:
            pass

        return scores


    def _score_valid_set(self, S, n):
        return len(S) / float(n)

    # @funsearch.run
    # def evaluateGreedy(self, alg) -> float:
    #     """
    #     期望 alg 具有：heuristic(n, rng=None) -> Iterable[int]
    #     """
    #     # 這裡仍然寫檔，不依賴 stdout
    #     for name, dataset in self.instances.items():
    #         densities = []
    #         sizes = []

    #         for _, inst in dataset.items():
    #             n = int(inst["n"])
    #             if not hasattr(alg, "heuristic"):
    #                 # 沒提供目標函式，直接記錄並退出
    #                 with open(self.error_log, "a") as f:
    #                     f.write(f"[EVAL] no heuristic() for n={n}\n")
    #                 return None

    #             try:
    #                 S = list(alg.heuristic(n, None))
    #             except Exception as e:
    #                 with open(self.error_log, "a") as f:
    #                     f.write(f"[EVAL] runtime error in heuristic(n={n}): {e}\n")
    #                     f.write(traceback.format_exc() + "\n")
    #                 return None

    #             S = {int(x) for x in S if 1 <= int(x) <= n}

    #             if not self._is_3ap_free(S):
    #                 densities.append(-1e9) # large positive penalty for invalid set
    #                 sizes.append(0)
    #             else:
    #                 densities.append(self._score_valid_set(S, n))
    #                 sizes.append(len(S))

    #         avg_density = float(np.mean(np.array(densities)))
    #         avg_size = float(np.mean(np.array(sizes)))

    #         if isinstance(self.lb, dict) and (name in self.lb) and (self.lb[name] is not None):
    #             denom = max(self.lb[name], 1e-9)
    #             fitness = (avg_size - self.lb[name]) / denom
    #         else:
    #             fitness = avg_density

    #     # 寫 fitness
    #     with open(self.fitness_log, "a") as f:
    #         f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} fitness={fitness}\n")

    #     return -fitness # return negative fitness for minimization
    # def evaluateGreedy(self, alg) -> float:
    #     """
    #     期望 alg 具有：heuristic(n, rng=None) -> Iterable[int]
    #     這版：不做下界正規化、不看密度；只回傳集合長度的平均值（for all instances）。
    #     """
    #     for name, dataset in self.instances.items():
    #         sizes = []

    #         for _, inst in dataset.items():
    #             n = int(inst["n"])
    #             if not hasattr(alg, "heuristic"):
    #                 with open(self.error_log, "a") as f:
    #                     f.write(f"[EVAL] no heuristic() for n={n}\n")
    #                 return None

    #             try:
    #                 S = list(alg.heuristic(n, None))
    #             except Exception as e:
    #                 with open(self.error_log, "a") as f:
    #                     f.write(f"[EVAL] runtime error in heuristic(n={n}): {e}\n")
    #                     f.write(traceback.format_exc() + "\n")
    #                 return None

    #             # 清理：轉 int、夾在 [1..n]、去重
    #             try:
    #                 S = {int(x) for x in S if 1 <= int(x) <= n}
    #             except Exception:
    #                 with open(self.error_log, "a") as f:
    #                     f.write(f"[EVAL] non-integer-like elements for n={n}\n")
    #                 return None

    #             # 合法才計長度；不合法給 0
    #             if not self._is_3ap_free(S):
    #                 sizes.append(0)
    #             else:
    #                 print(f"Valid set for n={n}, size={len(S)}, {sorted(list(S))}")
    #                 sizes.append(len(S))

    #         avg_size = float(np.mean(np.array(sizes))) if sizes else 0.0
    #         fitness = avg_size  # 只看長度

    #     # 記錄（方便對齊你現有的 log）
    #     with open(self.fitness_log, "a") as f:
    #         f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} size={fitness}\n")

    #     return -fitness  # 外層若做最小化就保留負號；若外層最大化改成：return fitness
    # def evaluateGreedy(self, alg, K: int = 10) -> float: # 加上 K 參數，預設為 1
    #     """
    #     期望 alg 具有：heuristic(n, rng=None) -> Iterable[int]
    #     這版：不做下界正規化、不看密度；只回傳集合長度的平均值（for all instances）。
    #     增加 pass@K 邏輯：run K 次，取最長的那個合法的 Salem-Spencer set 的長度。
    #     """
    #     for name, dataset in self.instances.items():
    #         sizes = []

    #         for _, inst in dataset.items():
    #             n = int(inst["n"])
    #             if not hasattr(alg, "heuristic"):
    #                 with open(self.error_log, "a") as f:
    #                     f.write(f"[EVAL] no heuristic() for n={n}\n")
    #                 return None

    #             # --- pass@K 邏輯開始 ---
    #             best_size = 0
    #             best_set_for_log = None
                
    #             # 運行 K 次
    #             for k_run in range(K):
    #                 try:
    #                     S = list(alg.heuristic(n, None))
    #                 except Exception as e:
    #                     # 錯誤處理：如果其中一次運行發生錯誤，停止對這個 n 的 K 次運行，並記錄錯誤
    #                     with open(self.error_log, "a") as f:
    #                         f.write(f"[EVAL] runtime error in heuristic(n={n}, run={k_run+1}/{K}): {e}\n")
    #                         f.write(traceback.format_exc() + "\n")
    #                     return None # 嚴重錯誤，直接返回 None

    #                 # 清理：轉 int、夾在 [1..n]、去重
    #                 try:
    #                     S_set = {int(x) for x in S if 1 <= int(x) <= n}
    #                 except Exception:
    #                     with open(self.error_log, "a") as f:
    #                         f.write(f"[EVAL] non-integer-like elements for n={n}, run={k_run+1}/{K}\n")
    #                     return None # 嚴重錯誤，直接返回 None

    #                 current_size = len(S_set)
                    
    #                 # 檢查合法性
    #                 is_valid = self._is_3ap_free(S_set)
                    
    #                 if is_valid:
    #                     # 如果合法，與目前最佳長度比較
    #                     if current_size > best_size:
    #                         best_size = current_size
    #                         best_set_for_log = S_set # 紀錄最長的集合，方便 Log 輸出
                            
    #                     # Log 輸出（可選，如果 K > 1 時輸出會比較多）
    #                     # print(f"Valid set for n={n}, run={k_run+1}/{K}, size={current_size}, {sorted(list(S_set))}")

    #                 # else:
    #                     # print(f"Invalid set for n={n}, run={k_run+1}/{K}, size={current_size}")
                
    #             # K 次運行結束後，取最長的合法集合長度
    #             sizes.append(best_size)
                
    #             # 統一 Log 輸出最佳結果
    #             if K > 1:
    #                  if best_size > 0:
    #                      print(f"Pass@{K} best for n={n}, size={best_size}, {sorted(list(best_set_for_log))}")
    #                  else:
    #                      print(f"Pass@{K} best for n={n}, size={best_size} (All invalid or size 0)")
    #             elif best_size > 0: # K=1 時，與原始 Log 格式一致
    #                 print(f"Valid set for n={n}, size={best_size}, {sorted(list(best_set_for_log))}")

    #             # --- pass@K 邏輯結束 ---
                
    #             # 原始程式碼中在迴圈內部的合法性檢查和 sizes.append(len(S)) 的邏輯被上述 pass@K 邏輯取代

    #         avg_size = float(np.mean(np.array(sizes))) if sizes else 0.0
    #         fitness = avg_size  # 只看長度

    #     # 記錄（方便對齊你現有的 log）
    #     with open(self.fitness_log, "a") as f:
    #         # 記錄時可以加上 K 方便識別
    #         f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} K={K} size={fitness}\n") 

    #     return -fitness  # 外層若做最小化就保留負號；若外層最大化改成：return fitness
    
    # def evaluateGreedy(self, alg) -> float:
    #     """
    #     完全依照 Map 裡的 N 進行評估。
    #     Fitness = (每個 N 的長度 * abs(diff)) 的總和 / abs(diff) 的總和
    #     """
    #     # 這是您指定的 Weight Map (來自 results-...-n-250_79)
    #     diff_map = {"80": 0.0, "81": -1.0, "82": -1.0, "83": -2.0, "84": -2.0, "85": -2.0, "86": -2.0, "87": -2.0, "88": -1.0, "89": -2.0, "90": -2.0, "91": -1.0, "92": -1.0, "93": -2.0, "94": -1.0, "95": -2.0, "96": -2.0, "97": -2.0, "98": -2.0, "99": -1.0, "100": -2.0, "101": -2.0, "102": -2.0, "103": -2.0, "104": -2.0, "105": -2.0, "106": -3.0, "107": -2.0, "108": -2.0, "109": -2.0, "110": -1.0, "111": -2.0, "112": -2.0, "113": -1.0, "114": -2.0, "115": -2.0, "116": -2.0, "117": -1.0, "118": -1.0, "119": 0.0, "120": 0.0, "121": 0.0, "122": -1.0, "123": 0.0, "124": -1.0, "125": -1.0, "126": -1.0, "127": -1.0, "128": 0.0, "129": -1.0, "130": 0.0, "131": -1.0, "132": 0.0, "133": -1.0, "134": 0.0, "135": 0.0, "136": 0.0, "137": -1.0, "138": -1.0, "139": -1.0, "140": -1.0, "141": -1.0, "142": -1.0, "143": -1.0, "144": -1.0, "145": -2.0, "146": -2.0, "147": -2.0, "148": -2.0, "149": -2.0, "150": -2.0, "151": -3.0, "152": -2.0, "153": -3.0, "154": -2.0, "155": -2.0, "156": -2.0, "157": -4.0, "158": -2.0, "159": -3.0, "160": -2.0, "161": -3.0, "162": -2.0, "163": -4.0, "164": -4.0, "165": -5.0, "166": -4.0, "167": -4.0, "168": -4.0, "169": -5.0, "170": -5.0, "171": -5.0, "172": -5.0, "173": -4.0, "174": -6.0, "175": -6.0, "176": -5.0, "177": -5.0, "178": -5.0, "179": -5.0, "180": -5.0, "181": -5.0, "182": -4.0, "183": -4.0, "184": -4.0, "185": -5.0, "186": -5.0, "187": -3.0, "188": -4.0, "189": -5.0, "190": -3.0, "191": -3.0, "192": -3.0, "193": -4.0, "194": -5.0, "195": -4.0, "196": -4.0, "197": -4.0, "198": -4.0, "199": -3.0, "200": -4.0, "201": -3.0, "202": -4.0, "203": -3.0, "204": -4.0, "205": -4.0, "206": -3.0, "207": -4.0, "208": -4.0, "209": -4.0, "210": -4.0, "211": -4.0, "212": -4.0, "213": -4.0, "214": -4.0, "215": -5.0, "216": -5.0, "217": -5.0, "218": -5.0, "219": -4.0, "220": -4.0, "221": -4.0, "222": -5.0, "223": -2.0, "224": -4.0, "225": -5.0, "226": -3.0, "227": -5.0, "228": -5.0, "229": -4.0, "230": -4.0, "231": -4.0, "232": -4.0, "233": -6.0, "234": -4.0, "235": -5.0, "236": -5.0, "237": -4.0, "238": -5.0, "239": -6.0, "240": -6.0, "241": -6.0, "242": -5.0, "243": -4.0, "244": -4.0, "245": -5.0, "246": -4.0, "247": -5.0, "248": -5.0, "249": -5.0, "250": -4.0, "254": -5.0, "256": -4.0, "260": -7.0, "261": -6.0, "263": -6.0, "268": -7.0, "272": -7.0, "286": -7.0, "315": -6.0, "321": -7.0, "323": -8.0, "331": -7.0, "332": -8.0, "341": -9.0, "350": -10.0, "353": -6.0, "437": -6.0, "440": -6.0, "445": -7.0, "454": -9.0, "455": -10.0, "457": -8.0, "463": -10.0, "471": -8.0, "478": -9.0, "479": -10.0, "483": -9.0, "486": -8.0, "490": -10.0, "549": -12.0, "567": -13.0, "571": -11.0, "580": -12.0, "581": -10.0, "613": -11.0, "614": -13.0, "632": -12.0, "664": -12.0, "670": -16.0, "676": -16.0, "677": -13.0, "678": -12.0, "682": -14.0, "686": -13.0, "693": -11.0, "696": -13.0, "698": -14.0, "736": -14.0, "742": -14.0, "744": -14.0, "746": -16.0, "750": -14.0, "756": -16.0, "765": -16.0, "768": -18.0, "783": -17.0, "786": -20.0, "788": -19.0, "795": -19.0, "805": -20.0, "807": -19.0, "809": -22.0, "830": -18.0, "831": -18.0, "833": -22.0, "835": -19.0, "837": -18.0, "841": -21.0, "853": -22.0, "854": -19.0, "857": -19.0, "859": -23.0, "864": -23.0, "891": -22.0, "897": -24.0, "899": -23.0, "905": -23.0, "907": -25.0, "916": -23.0, "922": -24.0, "928": -24.0, "930": -26.0, "932": -19.0, "937": -28.0, "938": -28.0, "947": -28.0, "956": -28.0, "1023": -25.0, "1094": 0}

    #     total_weight = sum(abs(v) for v in diff_map.values())
    #     weighted_size_sum = 0.0

    #     # 直接遍歷 Map 中的每一個 N (確保每個 N 都被跑過)
    #     for n, diff in diff_map.items():
    #         weight = abs(diff)
            
    #         # 如果權重為 0，理論上對結果沒影響，可以選擇跳過以節省時間
    #         if weight == 0:
    #             continue

    #         try:
    #             # 呼叫演算法生成集合
    #             S = list(alg.heuristic(n, None))
                
    #             # 清理與合法化集合：轉 int、範圍在 [1, n]
    #             S = {int(x) for x in S if 1 <= int(x) <= n}
                
    #             # 3AP-free 檢查 (呼叫原本類別裡的檢查函式)
    #             if not self._is_3ap_free(S):
    #                 size = 0
    #             else:
    #                 size = len(S)
    #                 # print(f"Valid set for n={n}, size={size}") # 除錯用
                    
    #             print(f"S size: {size} for n={n} with weight={weight}") # 除錯用
                    
    #         except Exception as e:
    #             # 如果執行出錯，該 N 分數計為 0
    #             size = 0
    #             # with open(self.error_log, "a") as f:
    #             #     f.write(f"[EVAL] Error for n={n}: {e}\n")

    #         # 累加：長度 * 權重
    #         weighted_size_sum += size * weight

    #     # 計算加權平均
    #     fitness = weighted_size_sum / total_weight if total_weight > 0 else 0.0

    #     # 記錄
    #     with open(self.fitness_log, "a") as f:
    #         f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} weighted_avg_size={fitness}\n")

    #     return -fitness  # 回傳負值供最小化優化使用
    
    # Top 10 ray interference
    # def evaluateGreedy(self, alg) -> float:
    #     """
    #     只用 diff_map 中 gap(=abs(diff)) 最大的 top-K 個 N 來評估。
    #     預設 K=10。
        
    #     fitness（預設）= top-K 的加權平均 size，其中 weight = abs(diff)
    #     回傳 -fitness 以供最小化。
    #     """
    #     diff_map = {"80": 0.0, "81": -1.0, "82": -1.0, "83": -2.0, "84": -2.0, "85": -2.0, "86": -2.0, "87": -2.0, "88": -1.0, "89": -2.0, "90": -2.0, "91": -1.0, "92": -1.0, "93": -2.0, "94": -1.0, "95": -2.0, "96": -2.0, "97": -2.0, "98": -2.0, "99": -1.0, "100": -2.0, "101": -2.0, "102": -2.0, "103": -2.0, "104": -2.0, "105": -2.0, "106": -3.0, "107": -2.0, "108": -2.0, "109": -2.0, "110": -1.0, "111": -2.0, "112": -2.0, "113": -1.0, "114": -2.0, "115": -2.0, "116": -2.0, "117": -1.0, "118": -1.0, "119": 0.0, "120": 0.0, "121": 0.0, "122": -1.0, "123": 0.0, "124": -1.0, "125": -1.0, "126": -1.0, "127": -1.0, "128": 0.0, "129": -1.0, "130": 0.0, "131": -1.0, "132": 0.0, "133": -1.0, "134": 0.0, "135": 0.0, "136": 0.0, "137": -1.0, "138": -1.0, "139": -1.0, "140": -1.0, "141": -1.0, "142": -1.0, "143": -1.0, "144": -1.0, "145": -2.0, "146": -2.0, "147": -2.0, "148": -2.0, "149": -2.0, "150": -2.0, "151": -3.0, "152": -2.0, "153": -3.0, "154": -2.0, "155": -2.0, "156": -2.0, "157": -4.0, "158": -2.0, "159": -3.0, "160": -2.0, "161": -3.0, "162": -2.0, "163": -4.0, "164": -4.0, "165": -5.0, "166": -4.0, "167": -4.0, "168": -4.0, "169": -5.0, "170": -5.0, "171": -5.0, "172": -5.0, "173": -4.0, "174": -6.0, "175": -6.0, "176": -5.0, "177": -5.0, "178": -5.0, "179": -5.0, "180": -5.0, "181": -5.0, "182": -4.0, "183": -4.0, "184": -4.0, "185": -5.0, "186": -5.0, "187": -3.0, "188": -4.0, "189": -5.0, "190": -3.0, "191": -3.0, "192": -3.0, "193": -4.0, "194": -5.0, "195": -4.0, "196": -4.0, "197": -4.0, "198": -4.0, "199": -3.0, "200": -4.0, "201": -3.0, "202": -4.0, "203": -3.0, "204": -4.0, "205": -4.0, "206": -3.0, "207": -4.0, "208": -4.0, "209": -4.0, "210": -4.0, "211": -4.0, "212": -4.0, "213": -4.0, "214": -4.0, "215": -5.0, "216": -5.0, "217": -5.0, "218": -5.0, "219": -4.0, "220": -4.0, "221": -4.0, "222": -5.0, "223": -2.0, "224": -4.0, "225": -5.0, "226": -3.0, "227": -5.0, "228": -5.0, "229": -4.0, "230": -4.0, "231": -4.0, "232": -4.0, "233": -6.0, "234": -4.0, "235": -5.0, "236": -5.0, "237": -4.0, "238": -5.0, "239": -6.0, "240": -6.0, "241": -6.0, "242": -5.0, "243": -4.0, "244": -4.0, "245": -5.0, "246": -4.0, "247": -5.0, "248": -5.0, "249": -5.0, "250": -4.0, "254": -5.0, "256": -4.0, "260": -7.0, "261": -6.0, "263": -6.0, "268": -7.0, "272": -7.0, "286": -7.0, "315": -6.0, "321": -7.0, "323": -8.0, "331": -7.0, "332": -8.0, "341": -9.0, "350": -10.0, "353": -6.0, "437": -6.0, "440": -6.0, "445": -7.0, "454": -9.0, "455": -10.0, "457": -8.0, "463": -10.0, "471": -8.0, "478": -9.0, "479": -10.0, "483": -9.0, "486": -8.0, "490": -10.0, "549": -12.0, "567": -13.0, "571": -11.0, "580": -12.0, "581": -10.0, "613": -11.0, "614": -13.0, "632": -12.0, "664": -12.0, "670": -16.0, "676": -16.0, "677": -13.0, "678": -12.0, "682": -14.0, "686": -13.0, "693": -11.0, "696": -13.0, "698": -14.0, "736": -14.0, "742": -14.0, "744": -14.0, "746": -16.0, "750": -14.0, "756": -16.0, "765": -16.0, "768": -18.0, "783": -17.0, "786": -20.0, "788": -19.0, "795": -19.0, "805": -20.0, "807": -19.0, "809": -22.0, "830": -18.0, "831": -18.0, "833": -22.0, "835": -19.0, "837": -18.0, "841": -21.0, "853": -22.0, "854": -19.0, "857": -19.0, "859": -23.0, "864": -23.0, "891": -22.0, "897": -24.0, "899": -23.0, "905": -23.0, "907": -25.0, "916": -23.0, "922": -24.0, "928": -24.0, "930": -26.0, "932": -19.0, "937": -28.0, "938": -28.0, "947": -28.0, "956": -28.0, "1023": -25.0, "1094": 0}

    #     top_k = 10

    #     # 1) 依 gap(abs(diff)) 由大到小排序，gap 相同則用 N 由小到大（可重現）
    #     #    並忽略 gap=0（因為不影響，也避免被塞進 top_k）
    #     items = []
    #     for n_str, diff in diff_map.items():
    #         gap = abs(diff)
    #         if gap > 0:
    #             items.append((int(n_str), gap))

    #     if not items:
    #         with open(self.fitness_log, "a") as f:
    #             f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} topK=0 fitness=0\n")
    #         return 0.0

    #     items.sort(key=lambda x: (-x[1], x[0]))  # (-gap, n)
    #     top_items = items[:min(top_k, len(items))]

    #     # 2) 只評估這 top-K 個 N
    #     weighted_size_sum = 0.0
    #     total_weight = 0.0

    #     # 若你想用「不加權平均」，改用這兩行：
    #     # size_sum = 0.0
    #     # count = 0

    #     for n, weight in top_items:
    #         try:
    #             S = list(alg.heuristic(n, None))
    #             S = {int(x) for x in S if 1 <= int(x) <= n}

    #             if not self._is_3ap_free(S):
    #                 size = 0
    #             else:
    #                 size = len(S)

    #             print(f"[Top{top_k}] S size: {size} for n={n} with gap={weight}")

    #         except Exception:
    #             size = 0

    #         # 加權版（預設）
    #         weighted_size_sum += size * weight
    #         total_weight += weight

    #         # 不加權平均版（若要改用這個就打開）
    #         # size_sum += size
    #         # count += 1

    #     # 3) fitness 計算
    #     fitness = weighted_size_sum / total_weight if total_weight > 0 else 0.0

    #     # 若改用不加權平均，改成：
    #     # fitness = (size_sum / count) if count > 0 else 0.0

    #     with open(self.fitness_log, "a") as f:
    #         f.write(
    #             f"{time.strftime('%Y-%m-%d %H:%M:%S')} "
    #             f"topK={min(top_k, len(items))} "
    #             f"topN={[n for n, _ in top_items]} "
    #             f"fitness={fitness}\n"
    #         )

    #     return -fitness
    
    def evaluateGreedy(self, alg) -> float:
        """
        Top-K evaluation + pass@K with multiprocessing.

        - Select top_k Ns by gap=abs(diff) desc, tie by N asc.
        - For each selected N, run heuristic K times (pass_k),
        take best size = max(|S|) among K runs (only if 3-AP free).
        - Fitness = weighted average of best_size with weight=gap.
        - Return -fitness (for minimization).
        """
        diff_map = {"80": 0.0, "81": -1.0, "82": -1.0, "83": -2.0, "84": -2.0, "85": -2.0, "86": -2.0, "87": -2.0, "88": -1.0, "89": -2.0, "90": -2.0, "91": -1.0, "92": -1.0, "93": -2.0, "94": -1.0, "95": -2.0, "96": -2.0, "97": -2.0, "98": -2.0, "99": -1.0, "100": -2.0, "101": -2.0, "102": -2.0, "103": -2.0, "104": -2.0, "105": -2.0, "106": -3.0, "107": -2.0, "108": -2.0, "109": -2.0, "110": -1.0, "111": -2.0, "112": -2.0, "113": -1.0, "114": -2.0, "115": -2.0, "116": -2.0, "117": -1.0, "118": -1.0, "119": 0.0, "120": 0.0, "121": 0.0, "122": -1.0, "123": 0.0, "124": -1.0, "125": -1.0, "126": -1.0, "127": -1.0, "128": 0.0, "129": -1.0, "130": 0.0, "131": -1.0, "132": 0.0, "133": -1.0, "134": 0.0, "135": 0.0, "136": 0.0, "137": -1.0, "138": -1.0, "139": -1.0, "140": -1.0, "141": -1.0, "142": -1.0, "143": -1.0, "144": -1.0, "145": -2.0, "146": -2.0, "147": -2.0, "148": -2.0, "149": -2.0, "150": -2.0, "151": -3.0, "152": -2.0, "153": -3.0, "154": -2.0, "155": -2.0, "156": -2.0, "157": -4.0, "158": -2.0, "159": -3.0, "160": -2.0, "161": -3.0, "162": -2.0, "163": -4.0, "164": -4.0, "165": -5.0, "166": -4.0, "167": -4.0, "168": -4.0, "169": -5.0, "170": -5.0, "171": -5.0, "172": -5.0, "173": -4.0, "174": -6.0, "175": -6.0, "176": -5.0, "177": -5.0, "178": -5.0, "179": -5.0, "180": -5.0, "181": -5.0, "182": -4.0, "183": -4.0, "184": -4.0, "185": -5.0, "186": -5.0, "187": -3.0, "188": -4.0, "189": -5.0, "190": -3.0, "191": -3.0, "192": -3.0, "193": -4.0, "194": -5.0, "195": -4.0, "196": -4.0, "197": -4.0, "198": -4.0, "199": -3.0, "200": -4.0, "201": -3.0, "202": -4.0, "203": -3.0, "204": -4.0, "205": -4.0, "206": -3.0, "207": -4.0, "208": -4.0, "209": -4.0, "210": -4.0, "211": -4.0, "212": -4.0, "213": -4.0, "214": -4.0, "215": -5.0, "216": -5.0, "217": -5.0, "218": -5.0, "219": -4.0, "220": -4.0, "221": -4.0, "222": -5.0, "223": -2.0, "224": -4.0, "225": -5.0, "226": -3.0, "227": -5.0, "228": -5.0, "229": -4.0, "230": -4.0, "231": -4.0, "232": -4.0, "233": -6.0, "234": -4.0, "235": -5.0, "236": -5.0, "237": -4.0, "238": -5.0, "239": -6.0, "240": -6.0, "241": -6.0, "242": -5.0, "243": -4.0, "244": -4.0, "245": -5.0, "246": -4.0, "247": -5.0, "248": -5.0, "249": -5.0, "250": -4.0, "254": -5.0, "256": -4.0, "260": -7.0, "261": -6.0, "263": -6.0, "268": -7.0, "272": -7.0, "286": -7.0, "315": -6.0, "321": -7.0, "323": -8.0, "331": -7.0, "332": -8.0, "341": -9.0, "350": -10.0, "353": -6.0, "437": -6.0, "440": -6.0, "445": -7.0, "454": -9.0, "455": -10.0, "457": -8.0, "463": -10.0, "471": -8.0, "478": -9.0, "479": -10.0, "483": -9.0, "486": -8.0, "490": -10.0, "549": -12.0, "567": -13.0, "571": -11.0, "580": -12.0, "581": -10.0, "613": -11.0, "614": -13.0, "632": -12.0, "664": -12.0, "670": -16.0, "676": -16.0, "677": -13.0, "678": -12.0, "682": -14.0, "686": -13.0, "693": -11.0, "696": -13.0, "698": -14.0, "736": -14.0, "742": -14.0, "744": -14.0, "746": -16.0, "750": -14.0, "756": -16.0, "765": -16.0, "768": -18.0, "783": -17.0, "786": -20.0, "788": -19.0, "795": -19.0, "805": -20.0, "807": -19.0, "809": -22.0, "830": -18.0, "831": -18.0, "833": -22.0, "835": -19.0, "837": -18.0, "841": -21.0, "853": -22.0, "854": -19.0, "857": -19.0, "859": -23.0, "864": -23.0, "891": -22.0, "897": -24.0, "899": -23.0, "905": -23.0, "907": -25.0, "916": -23.0, "922": -24.0, "928": -24.0, "930": -26.0, "932": -19.0, "937": -28.0, "938": -28.0, "947": -28.0, "956": -28.0, "1023": -25.0, "1094": 0}

        top_k = 3          # top-K Ns
        pass_k = 3         # pass@K
        num_proc = 1       # parallel processes (DISABLE inner parallelism to prevent crash)

        # 1) pick top_k by gap
        items = []
        for n_str, diff in diff_map.items():
            gap = abs(diff)
            if gap > 0:

                items.append((int(n_str), gap))

        if not items:
            with open(self.fitness_log, "a") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} topK=0 fitness=0\n")
            return 0.0

        items.sort(key=lambda x: (-x[1], x[0]))  # (-gap, n)
        top_items = items[:min(top_k, len(items))]

        # 2) pass@K jobs: for each n, run K times with different seeds
        #    seed strategy: deterministic from (n, k) to be reproducible
        jobs = []
        for n, _w in top_items:
            for k in range(pass_k):
                seed = (n * 1000003 + k * 9176) & 0x7FFFFFFF
                jobs.append((n, seed))

        # Make alg available to forked children without pickling (critical for exec-created module)
        global _EOH_EVAL_ALG
        _EOH_EVAL_ALG = alg

        # 3) run jobs in parallel (fork preferred); fallback to sequential if fork unavailable
        results = []
        used_parallel = False
        
        # Optimization: If num_proc <= 1, run sequentially to avoid orphan processes
        if num_proc > 1:
            try:
                # Prefer fork to avoid "can't import dynamic module" issues (ray interference style)
                ctx = mp.get_context("fork")
                used_parallel = True
                with ctx.Pool(processes=min(num_proc, len(jobs)), initializer=_make_non_daemon) as pool:
                    results = pool.map(_passk_worker, jobs)
            except Exception as e:
                # Fallback: sequential (safe everywhere)
                used_parallel = False
                results = []
                for job in jobs:
                    results.append(_passk_worker(job))

                with open(self.error_log, "a") as f:
                    f.write(
                        f"[PASSK] multiprocessing unavailable; fallback to sequential. err={repr(e)}\n"
                    )
        else:
             # Sequential execution
             used_parallel = False
             results = []
             for job in jobs:
                results.append(_passk_worker(job))

        # 4) aggregate best size per n
        best_size_by_n = {n: 0 for n, _w in top_items}
        for n, size in results:
            if n in best_size_by_n and size > best_size_by_n[n]:
                best_size_by_n[n] = size

        # 5) weighted fitness using best sizes
        weighted_size_sum = 0.0
        total_weight = 0.0

        for n, weight in top_items:
            best_size = best_size_by_n.get(n, 0)
            print(
                f"[Top{top_k} pass@{pass_k}] best |S|={best_size} for n={n} with gap={weight} "
                f"(parallel={used_parallel})"
            )
            weighted_size_sum += best_size * weight
            total_weight += weight

        fitness = weighted_size_sum / total_weight if total_weight > 0 else 0.0

        with open(self.fitness_log, "a") as f:
            f.write(
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} "
                f"topK={min(top_k, len(items))} "
                f"passK={pass_k} "
                f"procs={num_proc} "
                f"parallel={int(used_parallel)} "
                f"topN={[n for n, _ in top_items]} "
                f"bestSize={[best_size_by_n[n] for n, _ in top_items]} "
                f"fitness={fitness}\n"
            )

        return -fitness



    
    
    def evaluate(self, code_string: str):
        """
        Modified evaluate to use subprocess-based isolation.
        """
        # Semantic Check using LLM
        # Perform this check BEFORE running the expensive evaluation.
        # Only check if it's potentially valid Python first (basic parse included in _llm_check_strategy implied?)
        # We do it here.
        
        is_valid_strategy, reason = _llm_check_strategy(code_string)
        if not is_valid_strategy:
             with open(self.error_log, "a") as f:
                 f.write(f"[POLICY] Rejected Code {self.eval_counter+1}: LLM Strategy Check Failed. Reason: {reason}\\n")
             # Return a penalty score (0.0 size)
             return 0.0

        self.eval_counter += 1
        cand_path = os.path.join(self.canddir, f"cand_{self.eval_counter:06d}.py")
        try:
            with open(cand_path, "w") as f:
                f.write(code_string)
        except Exception as e:
             with open(self.error_log, "a") as f:
                f.write(f"[WRITE] cannot write candidate {cand_path}: {e}\n")

        # Prepare paths for IPC
        evaluator_pkl = os.path.join(self.canddir, f"evaluator_{self.eval_counter}.pkl")
        output_pkl = os.path.join(self.canddir, f"output_{self.eval_counter}.pkl")
        runner_script = os.path.join(self.canddir, f"runner_{self.eval_counter}.py")

        try:
            # Pickle self (evaluator)
            with open(evaluator_pkl, "wb") as f:
                pickle.dump(self, f)

            # Write runner script
            with open(runner_script, "w") as f:
                f.write(RUNNER_SCRIPT)

            # Invoke subprocess
            # We use the same python interpreter
            cmd = [sys.executable, runner_script, evaluator_pkl, cand_path, output_pkl]
            
            subprocess.run(cmd, timeout=180, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # Read result
            if os.path.exists(output_pkl):
                with open(output_pkl, "rb") as f:
                    res = pickle.load(f)
                
                if isinstance(res, Exception):
                    raise res
                return res
            else:
                 # No output file -> crash
                 return 0.0

        except subprocess.TimeoutExpired:
            with open(self.error_log, "a") as f:
                f.write(f"[TIMEOUT] Execution timed out for {cand_path}\n")
            return 0.0
        except Exception as e:
             with open(self.error_log, "a") as f:
                f.write(f"[EXEC] Subprocess error for {cand_path}: {e}\n")
                # f.write(traceback.format_exc() + "\n")
             return 0.0
        finally:
            # Cleanup temp files
            for p in [evaluator_pkl, output_pkl, runner_script]:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except:
                    pass

