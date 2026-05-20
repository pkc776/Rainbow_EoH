import numpy as np
import time
from .eoh_evolution import Evolution
import warnings
from joblib import Parallel, delayed
from .evaluator_accelerate import add_numba_decorator
import re
import concurrent.futures
from ...utils.dedup_utils import get_ast_hash
from ..island_model import ParentSelector, IslandGenerator
import random

seen_program_hashes = set()

class InterfaceEC():
    def __init__(self, pop_size, m, api_endpoint, api_key, llm_model,llm_use_local,llm_local_url, debug_mode, interface_prob, select,n_p,timeout,use_numba,**kwargs):

        # LLM settings
        self.pop_size = pop_size
        self.interface_eval = interface_prob
        prompts = interface_prob.prompts
        self.evol = Evolution(api_endpoint, api_key, llm_model,llm_use_local,llm_local_url, debug_mode,prompts, **kwargs)
        self.m = m
        self.debug = debug_mode
        self.parent_selector = ParentSelector()
        self.island_generator = IslandGenerator(task_prompt=prompts.get_inout_inf() + "\n" + prompts.get_other_inf())

        if not self.debug:
            warnings.filterwarnings("ignore")

        self.select = select
        self.n_p = n_p
        
        self.timeout = timeout
        self.use_numba = use_numba
        
    def code2file(self,code):
        with open("./ael_alg.py", "w") as file:
        # Write the code to the file
            file.write(code)
        return 
    
    def add2pop(self,population,offspring):
        for ind in population:
            # print(f"[ind] = {ind}, ind['objective'] = {ind['objective']}, offspring['objective'] = {offspring['objective']}")
            if ind['objective'] == offspring['objective']:
                if self.debug:
                    print("duplicated result, retrying ... ")
                    a = 1/0
                return False
        population.append(offspring)
        return True
    
    def check_duplicate(self,population,code):
        for ind in population:
            if code == ind['code']:
                return True
        return False

    # def population_management(self,pop):
    #     # Delete the worst individual
    #     pop_new = heapq.nsmallest(self.pop_size, pop, key=lambda x: x['objective'])
    #     return pop_new
    
    # def parent_selection(self,pop,m):
    #     ranks = [i for i in range(len(pop))]
    #     probs = [1 / (rank + 1 + len(pop)) for rank in ranks]
    #     parents = random.choices(pop, weights=probs, k=m)
    #     return parents

    def population_generation(self):
        
        n_create = 2
        
        population = []

        for i in range(n_create):
            _,pop = self.get_algorithm([],'i1')
            for p in pop:
                population.append(p)
             
        return population
    
    def population_generation_seed(self,seeds,n_p):

        population = []

        fitness = Parallel(n_jobs=n_p)(delayed(self.interface_eval.evaluate)(seed['code']) for seed in seeds)

        for i in range(len(seeds)):
            try:
                seed_alg = {
                    'algorithm': seeds[i]['algorithm'],
                    'code': seeds[i]['code'],
                    'objective': None,
                    'other_inf': None
                }

                obj = np.array(fitness[i])
                seed_alg['objective'] = np.round(obj, 5)
                population.append(seed_alg)

            except Exception as e:
                print("Error in seed algorithm")
                exit()

        print("Initiliazation finished! Get "+str(len(seeds))+" seed algorithms")

        return population
    

    def _get_alg(self,pop,operator):
        offspring = {
            'algorithm': None,
            'code': None,
            'objective': None,
            'other_inf': None
        }
        if operator == "i1":
            parents = None
            [offspring['code'],offspring['algorithm']] =  self.evol.i1()            
        else:
            # Map operator to island settings
            k = 1 if operator.startswith('m') else 2
            
            if operator == 'e1':
                island_type, agg = 'greedy_island', 'high'
            elif operator == 'e2':
                island_type, agg = 'greedy_island', 'low'
            elif operator == 'm1':
                island_type, agg = 'stochastic_island', 'high'
            elif operator == 'm2':
                island_type, agg = 'stochastic_island', 'low'
            else:
                island_type, agg = 'greedy_island', 'low'

            parents = self.parent_selector.sample_diverse_parents(pop, k=k)
            
            # Guard in case the population was empty or valid pareto filtering returned fewer
            if not parents:
                import random
                parents = [random.choice(pop) for _ in range(k)]
                
            import os
            use_m5 = os.environ.get("ABLATION_M5", "1") == "1"
            
            if not use_m5:
                if operator == "e1":
                    [offspring['code'],offspring['algorithm']] = self.evol.e1(parents)
                elif operator == "e2":
                    [offspring['code'],offspring['algorithm']] = self.evol.e2(parents) 
                elif operator == "m1":
                    [offspring['code'],offspring['algorithm']] = self.evol.m1(parents[0])   
                elif operator == "m2":
                    [offspring['code'],offspring['algorithm']] = self.evol.m2(parents[0]) 
                elif operator == "m3":
                    [offspring['code'],offspring['algorithm']] = self.evol.m3(parents[0]) 
            else:
                prompt = self.island_generator.build_prompt(parents, island_type, agg)
                res = self.evol._get_alg(prompt)
                if len(res) == 2:
                    offspring['code'], offspring['algorithm'] = res[0], res[1]

        return parents, offspring

    def get_offspring(self, pop, operator):

        try:
            p, offspring = self._get_alg(pop, operator)
            
            if self.use_numba:
                
                # Regular expression pattern to match function definitions
                pattern = r"def\s+(\w+)\s*\(.*\):"

                # Search for function definitions in the code
                match = re.search(pattern, offspring['code'])

                function_name = match.group(1)

                code = add_numba_decorator(program=offspring['code'], function_name=function_name)
            else:
                code = offspring['code']

            n_retry= 1
            while True:
                # Check for duplicate string
                is_dup_str = self.check_duplicate(pop, offspring['code'])
                # Check for duplicate AST hash
                ast_hash = get_ast_hash(offspring['code'])
                is_dup_ast = ast_hash in seen_program_hashes
                
                if not is_dup_str and not is_dup_ast:
                    seen_program_hashes.add(ast_hash)
                    break
                
                n_retry += 1
                if self.debug:
                    print("duplicated code (string or AST hash), wait 1 second and retrying ... ")
                    
                p, offspring = self._get_alg(pop, operator)

                if self.use_numba:
                    # Regular expression pattern to match function definitions
                    pattern = r"def\s+(\w+)\s*\(.*\):"

                    # Search for function definitions in the code
                    match = re.search(pattern, offspring['code'])

                    function_name = match.group(1)

                    code = add_numba_decorator(program=offspring['code'], function_name=function_name)
                else:
                    code = offspring['code']
                    
                if n_retry > 1:
                    break
                
                
            #self.code2file(offspring['code'])
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self.interface_eval.evaluate, code)
                fitness = future.result(timeout=self.timeout)
                # Ensure fitness isn't wrapped in np.round if it's a dictionary
                if isinstance(fitness, dict):
                    offspring['objective'] = fitness
                else:
                    offspring['objective'] = np.round(fitness, 5)
                future.cancel()        
                # fitness = self.interface_eval.evaluate(code)
                

        except Exception as e:

            offspring = {
                'algorithm': None,
                'code': None,
                'objective': None,
                'other_inf': None
            }
            p = None

        # Round the objective values
        return p, offspring
    # def process_task(self,pop, operator):
    #     result =  None, {
    #             'algorithm': None,
    #             'code': None,
    #             'objective': None,
    #             'other_inf': None
    #         }
    #     with concurrent.futures.ThreadPoolExecutor() as executor:
    #         future = executor.submit(self.get_offspring, pop, operator)
    #         try:
    #             result = future.result(timeout=self.timeout)
    #             future.cancel()
    #             #print(result)
    #         except:
    #             future.cancel()
                
    #     return result

    
    def get_algorithm(self, pop, operator):
        results = []
        try:
            results = Parallel(n_jobs=self.n_p,timeout=self.timeout * 2)(delayed(self.get_offspring)(pop, operator) for _ in range(self.pop_size))
        except Exception as e:
            if self.debug:
                print(f"Error: {e}")
            print("Parallel time out .")
            
        time.sleep(2)


        out_p = []
        out_off = []

        for p, off in results:
            out_p.append(p)
            out_off.append(off)
            if self.debug:
                print(f">>> check offsprings: \n {off}")
        return out_p, out_off
    # def get_algorithm(self,pop,operator, pop_size, n_p):
        
    #     # perform it pop_size times with n_p processes in parallel
    #     p,offspring = self._get_alg(pop,operator)
    #     while self.check_duplicate(pop,offspring['code']):
    #         if self.debug:
    #             print("duplicated code, wait 1 second and retrying ... ")
    #         time.sleep(1)
    #         p,offspring = self._get_alg(pop,operator)
    #     self.code2file(offspring['code'])
    #     try:
    #         fitness= self.interface_eval.evaluate()
    #     except:
    #         fitness = None
    #     offspring['objective'] =  fitness
    #     #offspring['other_inf'] =  first_gap
    #     while (fitness == None):
    #         if self.debug:
    #             print("warning! error code, retrying ... ")
    #         p,offspring = self._get_alg(pop,operator)
    #         while self.check_duplicate(pop,offspring['code']):
    #             if self.debug:
    #                 print("duplicated code, wait 1 second and retrying ... ")
    #             time.sleep(1)
    #             p,offspring = self._get_alg(pop,operator)
    #         self.code2file(offspring['code'])
    #         try:
    #             fitness= self.interface_eval.evaluate()
    #         except:
    #             fitness = None
    #         offspring['objective'] =  fitness
    #         #offspring['other_inf'] =  first_gap
    #     offspring['objective'] = np.round(offspring['objective'],5) 
    #     #offspring['other_inf'] = np.round(offspring['other_inf'],3)
    #     return p,offspring
