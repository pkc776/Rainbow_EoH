class GetPrompts():
    def __init__(self):
        import os
        # 任務：為固定 n 構造一個儘可能大的 3-AP-free 子集合 S ⊆ {1..n}
        self.prompt_task = (
            "I need help designing a constructive heuristic that builds a large Salem–Spencer set.\n"
            # "Given an integer n, return a subset S of {1, 2, ..., n} with no three-term arithmetic progression "
            "Given an integer n=N, return a subset S of {1, 2, ..., N} with no three-term arithmetic progression "
            "(i.e., there must not exist a, b, c in S with a + c = 2*b). The goal is to maximize |S|."
        )

        # 要生成的函式名稱與介面（EoH 會動態載入並呼叫）
        self.prompt_func_name = "heuristic"
        self.prompt_func_inputs = ["n", "rng"]
        self.prompt_func_outputs = ["S"]

        # I/O 說明
        self.prompt_inout_inf = (
            "'n' is a positive integer specifying the universe {1..n}. We are only interested in n=N, try find the largest 3-AP-free subset for this specific n and don't worry about other number of n."
            "'rng' is a random seed or a numpy Generator; the function should be deterministic "
            "for the same (n, rng). Return 'S' as a Python list (or tuple) of unique integers strictly in [1..N]. "
            "S must be 3-AP-free: there must be no (a, b, c) in S with a + c = 2*b."
            "Then size of S should be as large as possible."
            # "The size of S may satisfy known lower bounds for Salem–Spencer sets (Szekeres conjecture), which is at least 2^(log(2*n)/log(3))."
        )

        math_prior = (
            "To effectively avoid Arithmetic Progressions of length 3, you should analyze numbers by converting them into different bases. You have access to the function get_digits(num, base). Explore how the distribution, sums, or mathematical patterns of these digits can help you prioritize numbers.\n"
        ) if os.environ.get("ABLATION_M1", "1") == "1" else ""
        
        self.prompt_other_inf = (
            math_prior +
            "Constraints & tips:\n"
            "- Use only the standard library and 'numpy' (already available). Do not read/write files or print.\n"
            "- Keep it fast: aim for roughly O(n log n) or O(n * sqrt(n)) behavior for n up to a few thousands.\n"
            "- Ensure determinism given the same inputs (e.g., derive a local numpy RNG from 'rng').\n"
            "- Ensure determinism given the same inputs (e.g., derive a local numpy RNG from 'rng').\n"
            "- The function MUST return a valid 3-AP-free set. If you implement helpers, keep everything in one file.\n"
            "- Example signature to implement:\n"
            "    def heuristic(n, rng=None):\n"
            "        # build and return a list of integers in [1..n]\n"
            "- No global state, no external dependencies.\n"
            "\n"
            "**CRITICAL STRATEGY REQUIREMENT**: Ternary Structure / Inductive Construction\n"
            "1. **Core Strategy**: You MUST construct the set by splitting the range [1, N] into three parts (Low, Middle, High).\n"
            "2. **Construction Logic**: Fill the Low part [1, N/3] and the High part [2N/3, N] using a solution derived from a smaller n.\n"
            "3. **Middle Gap**: Leave the Middle part largely empty to avoid arithmetic progressions intersecting the Low and High parts.\n"
            "4. **Inductive Nature**: The solution for size N should be built from the solution for size ~N/3 (or similar smaller block). Explicit recursion is good but NOT required; iterative bottom-up construction is accepted.\n"
            "5. **Forbidden**: Do NOT use simple linear greedy scanning that ignores this 3-part structure."
        )

    def get_task(self):
        return self.prompt_task
    
    def get_func_name(self):
        return self.prompt_func_name
    
    def get_func_inputs(self):
        return self.prompt_func_inputs
    
    def get_func_outputs(self):
        return self.prompt_func_outputs
    
    def get_inout_inf(self):
        return self.prompt_inout_inf

    def get_other_inf(self):
        return self.prompt_other_inf
