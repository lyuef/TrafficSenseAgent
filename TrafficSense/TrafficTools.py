
def traffictool(name,description):
    def decorator(func) :
        func.name = name
        func.description = description
        return func
    
    return decorator

class demo_longhua_simulation :
    def __init__(self):
        pass
    
    @traffictool(name="demo_longhua_simulation",
                 description="""
                When the user wants you to tell him the traffic conditions in Longhua District, Shenzhen, it will return the current analysis of the traffic conditions in Longhua District, Shenzhen.
"""
                 )
    def inference(self,input_param:str) -> str :
        return "It is the peak season for returning to China during the summer vacation. Traffic is very congested at Shenzhen North Station and its surrounding areas in Longhua District, Shenzhen."
    
class demo_longhua_solution : 
    def __init__(self):
        pass

    @traffictool(name="demo_longhua_simulation",
                 description="""When the user wants you to solve the traffic congestion in Longhua District, the following suggestions will be returned"""
                 )
    def inference(self,input_param:str) ->str :
        return "使用长度边权的基于局部搜索的最优路径分配算法实现的协同路径优化方法解决拥堵"
class demo_longhua_result :
    def __init__(self):
        pass

    @traffictool(name="demo_longhua_result",
                 description="当用户使用了长度边权的基于局部搜索的最优路径分配算法实现的协同路径优化方法的结果"
                 )
    def inference(self,input_param:str)->str :
        return "When the algorithm was used, simulation results showed that congestion was successfully alleviated."