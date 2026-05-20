import random
from .management.pop_greedy import is_dominated
from ..utils.dedup_utils import get_ast_hash

class ParentSelector:
    def __init__(self):
        pass

    def sample_diverse_parents(self, population, k=2):
        """
        Rank-based + Novelty Bonus Selection
        """
        # Filter for valid dict objectives
        valid_pop = [ind for ind in population if isinstance(ind.get('objective'), dict)]
        if not valid_pop:
            # Fallback if Pareto evaluation isn't available
            return random.sample(population, min(k, len(population)))

        # 1. Pareto Front sorting (Quality)
        unique_pop = []
        seen_objs = set()
        for ind in valid_pop:
            obj_tuple = tuple(sorted(ind['objective'].items()))
            if obj_tuple not in seen_objs:
                seen_objs.add(obj_tuple)
                unique_pop.append(ind)

        # Sort into Pareto Fronts
        for p_id, p_ind in enumerate(unique_pop):
            p_ind['_domcount'] = 0
            p_ind['_domset'] = []
            for q_id, q_ind in enumerate(unique_pop):
                if p_id == q_id: continue
                if is_dominated(q_ind['objective'], p_ind['objective']):
                    # p dominates q
                    p_ind['_domset'].append(q_ind)
                elif is_dominated(p_ind['objective'], q_ind['objective']):
                    # q dominates p
                    p_ind['_domcount'] += 1

        fronts = []
        curr_front = [p for p in unique_pop if p['_domcount'] == 0]
        while curr_front:
            fronts.append(curr_front)
            next_front = []
            for p in curr_front:
                for q in p['_domset']:
                    q['_domcount'] -= 1
                    if q['_domcount'] == 0:
                        next_front.append(q)
            curr_front = next_front

        # 2. Diverse Top-k Selection (Diversity via AST Hashes)
        selected = []
        selected_hashes = set()
        
        import os
        use_m2 = os.environ.get("ABLATION_M2", "1") == "1"

        for front in fronts:
            # Shuffle the front to give equal chance to individuals on the same Pareto tier
            random.shuffle(front)
            for ind in front:
                if not use_m2:
                    selected.append(ind)
                else:
                    ast_hash = get_ast_hash(ind['code'])
                    # Ensure we only pick structurally distinct parents
                    if ast_hash not in selected_hashes:
                        selected.append(ind)
                        selected_hashes.add(ast_hash)
                
                if len(selected) == k:
                    break
            if len(selected) == k:
                break

        # Cleanup temporary keys
        for ind in unique_pop:
            ind.pop('_domcount', None)
            ind.pop('_domset', None)

        return selected

class IslandGenerator:
    def __init__(self, task_prompt=""):
        self.task_prompt = task_prompt

    def build_prompt(self, parents, island_type="greedy_island", aggressiveness="low"):
        """
        Dynamically builds the LLM prompt using requested island constraints and macro/micro mutations.
        """
        prompt = self.task_prompt + "\n\n"

        # 1. Island Specification
        if island_type == "greedy_island":
            prompt += "ISLAND STRATEGY: Focus on deterministic, greedy heuristic construction. Avoid randomness.\n"
        elif island_type == "stochastic_island":
            prompt += "ISLAND STRATEGY: Focus on incorporating smart stochastic choices (like random sampling or perturbation) within the construction.\n"

        # 2. Aggressiveness
        if aggressiveness == "high":
            prompt += "AGGRESSIVENESS: HIGH. Completely rewrite the core logic. Introduce a radically different mathematical invariant or fundamentally new strategy.\n"
        else:
            prompt += "AGGRESSIVENESS: LOW. Perform small local tweaks or minor refinements to the existing logic.\n"

        # 3. Operator Policy (Mutation vs Crossover)
        if len(parents) == 1:
            prompt += "\nApply a MUTATION operation on the following parent code:\n"
            prompt += f"```python\n{parents[0]['code']}\n```\n"
        elif len(parents) >= 2:
            prompt += "\nApply a CROSSOVER operation. Blend the best mathematical insights and logic from the following parents:\n"
            prompt += f"Parent 1:\n```python\n{parents[0]['code']}\n```\n"
            prompt += f"Parent 2:\n```python\n{parents[1]['code']}\n```\n"

        # Explicit layout instructions for LLM parsing
        prompt += "\nFirst, describe your new algorithm and main steps in one sentence. The description must be inside a brace {}. "
        prompt += "Next, implement it in Python as a single function. Keep the function name, inputs, and outputs as requested in the task. Do not give additional explanations."

        return prompt
