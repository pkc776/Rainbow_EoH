# eoh/problems/optimization/salem_spencer/get_instance.py
import os

class GetData:
    def __init__(self, n=None, default_n=1094):
        """
        n: 可直接傳入的 n。若為 None，會讀環境變數 SALEM_N，最後才用 default_n。
        """
        if n is None:
            raw = os.getenv("SALEM_N", "").strip()
            # 小心空字串或亂值
            if raw.isdigit():
                n = int(raw)
            else:
                n = default_n

        # 基本驗證
        if not isinstance(n, int) or n <= 0:
            raise ValueError(f"Invalid n={n}. n must be a positive integer.")

        self.n = n

    def get_instances(self):
        instances = {
            "single_n": {
                "target": {"n": self.n}
            }
        }
        lb = {}  # 沒有下界就留空
        return instances, lb
