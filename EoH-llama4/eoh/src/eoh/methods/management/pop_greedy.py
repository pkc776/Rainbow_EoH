import heapq
import os

def is_dominated(scores_A: dict, scores_B: dict) -> bool:
    """
    Returns True if Program A is dominated by Program B.
    B dominates A if B >= A in all objectives, and B > A in at least one.
    (Maximization for all dimensions)
    """
    if len(scores_A) != len(scores_B) or scores_A.keys() != scores_B.keys():
        return False
        
    if os.environ.get("ABLATION_M3", "1") == "0":
        # Disable Pareto: collapse to sum
        sum_a = sum(scores_A.values())
        sum_b = sum(scores_B.values())
        return sum_b > sum_a
    
    # Program A is dominated by Program B if scores_B[n] >= scores_A[n] for ALL n
    # AND scores_B[n] > scores_A[n] for AT LEAST ONE n
    geq = all(scores_B[n] >= scores_A[n] for n in scores_A)
    strict_gr = any(scores_B[n] > scores_A[n] for n in scores_A)
    return geq and strict_gr

def population_management(pop, size):
    # Filter out individuals without valid dictionary objectives
    valid_pop = [ind for ind in pop if isinstance(ind.get('objective'), dict)]
    
    if not valid_pop:
        # Fallback to normal float minimization logic if Pareto is disabled or failed
        num_pop = [ind for ind in pop if isinstance(ind.get('objective'), (int, float))]
        if not num_pop: return []
        num_size = min(size, len(num_pop))
        unique_pop = []
        unique_obj = set()
        for ind in num_pop:
            if ind['objective'] not in unique_obj:
                unique_obj.add(ind['objective'])
                unique_pop.append(ind)
        return heapq.nsmallest(num_size, unique_pop, key=lambda x: x['objective'])

    # Keep only unique objectives to encourage diversity
    unique_pop = []
    seen_objs = set()
    for ind in valid_pop:
        obj_tuple = tuple(sorted(ind['objective'].items()))
        if obj_tuple not in seen_objs:
            seen_objs.add(obj_tuple)
            unique_pop.append(ind)

    # Perform Non-Dominated Sorting
    fronts = []
    current_front = []
    
    # Reset Pareto data
    for p_id, p_ind in enumerate(unique_pop):
        p_ind['_domination_count'] = 0
        p_ind['_dominated_set'] = []
        
        for q_id, q_ind in enumerate(unique_pop):
            if p_id == q_id: continue
            if is_dominated(q_ind['objective'], p_ind['objective']):
                # p dominates q
                p_ind['_dominated_set'].append(q_ind)
            elif is_dominated(p_ind['objective'], q_ind['objective']):
                # q dominates p
                p_ind['_domination_count'] += 1
                
        if p_ind['_domination_count'] == 0:
            current_front.append(p_ind)
            
    while current_front:
        fronts.append(current_front)
        next_front = []
        for p_ind in current_front:
            for q_ind in p_ind['_dominated_set']:
                q_ind['_domination_count'] -= 1
                if q_ind['_domination_count'] == 0:
                    next_front.append(q_ind)
        current_front = next_front
        
    pop_new = []
    # Fill pop_new with fronts until we hit size 
    # (If we wanted purely to protect sizes, we could just return front 0, but EoH needs padding)
    for front in fronts:
        # Sort within front by sum of sizes to break ties consistently (larger is better)
        front_sorted = sorted(front, key=lambda x: sum(x['objective'].values()), reverse=True)
        if len(pop_new) + len(front_sorted) <= size:
            pop_new.extend(front_sorted)
        else:
            remain = size - len(pop_new)
            pop_new.extend(front_sorted[:remain])
            break
            
    # Cleanup pseudo keys
    for ind in pop_new:
        ind.pop('_domination_count', None)
        ind.pop('_dominated_set', None)
        
    return pop_new