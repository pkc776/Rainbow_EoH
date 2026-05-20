# import http.client
# import json


# class InterfaceAPI:
#     def __init__(self, api_endpoint, api_key, model_LLM, debug_mode):
#         self.api_endpoint = api_endpoint
#         self.api_key = api_key
#         self.model_LLM = model_LLM
#         self.debug_mode = debug_mode
#         self.n_trial = 5

#     def get_response(self, prompt_content):
#         payload_explanation = json.dumps(
#             {
#                 "model": self.model_LLM,
#                 "messages": [
#                     # {"role": "system", "content": "You are a helpful assistant."},
#                     {"role": "user", "content": prompt_content}
#                 ],
#             }
#         )

#         headers = {
#             "Authorization": "Bearer " + self.api_key,
#             "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
#             "Content-Type": "application/json",
#             "x-api2d-no-cache": 1,
#         }
        
#         response = None
#         n_trial = 1
#         while True:
#             n_trial += 1
#             if n_trial > self.n_trial:
#                 return response
#             try:
#                 conn = http.client.HTTPSConnection(self.api_endpoint)
#                 conn.request("POST", "/v1/chat/completions", payload_explanation, headers)
#                 res = conn.getresponse()
#                 data = res.read()
#                 json_data = json.loads(data)
#                 response = json_data["choices"][0]["message"]["content"]
#                 break
#             except:
#                 if self.debug_mode:
#                     print("Error in API. Restarting the process...")
#                 continue
            

#         return response

import http.client
import json
import time
from urllib.parse import urlparse

class InterfaceAPI:
    def __init__(self, api_endpoint, api_key, model_LLM, debug_mode, timeout=30, n_trial=5):
        """
        api_endpoint can be either:
          - host only: "inner-medusa.genai.nchc.org.tw"
          - full url:  "https://inner-medusa.genai.nchc.org.tw/v1"
        """
        self.api_key = api_key
        self.model_LLM = model_LLM
        self.debug_mode = debug_mode
        self.timeout = timeout
        self.n_trial = n_trial

        parsed = urlparse(api_endpoint if "://" in api_endpoint else f"https://{api_endpoint}")
        self.scheme = parsed.scheme or "https"
        self.host = parsed.netloc or parsed.path  # if user passed just hostname
        self.base_path = parsed.path.rstrip("/")  # e.g., "/v1" or ""

        # default to HTTPS unless explicitly http://
        self._Conn = http.client.HTTPConnection if self.scheme == "http" else http.client.HTTPSConnection

    def _request_path(self):
        # final endpoint path: "<base_path>/chat/completions"
        base = self.base_path if self.base_path else ""
        return f"{base}/chat/completions"

    def get_response(self, prompt_content):
        payload = json.dumps({
            "model": self.model_LLM,
            "messages": [
                {"role": "user", "content": prompt_content}
            ],
        })

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "EoH/1.0",
        }

        last_error = None
        for attempt in range(1, self.n_trial + 1):
            conn = None
            try:
                conn = self._Conn(self.host, timeout=self.timeout)
                conn.request("POST", self._request_path(), payload, headers)
                res = conn.getresponse()
                body = res.read()
                print(f"res.status = {res.status}, body = {body}")
                if res.status != 200:
                    # try to extract error info
                    try:
                        err = json.loads(body)
                    except Exception:
                        err = {"raw": body.decode("utf-8", errors="ignore")}
                    if self.debug_mode:
                        print(f"[Attempt {attempt}] HTTP {res.status}: {err}")
                    last_error = RuntimeError(f"HTTP {res.status}")
                    # retry on non-200 too
                    time.sleep(min(2 ** attempt, 10))
                    continue

                data = json.loads(body)
                return data["choices"][0]["message"]["content"]

            except Exception as e:
                last_error = e
                if self.debug_mode:
                    print(f"[Attempt {attempt}] Error: {e}. Retrying...")
                time.sleep(min(2 ** attempt, 10))
                continue
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

        # All retries failed
        if self.debug_mode and last_error:
            print(f"Failed after {self.n_trial} attempts. Last error: {last_error}")
        return None
