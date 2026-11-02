import pandas as pd
import numpy as np 
data={
    "student":["A","B","C","D","E","F"],
    "attendance":[85,90,np.nan,75,80,95],
    "Study hours":[3,4,2,np.nan,5,6],
    "Assignment score":[80,np.nan,60,70,90,95],
    "previous marks":[75,82,65,72,np.nan,88]
}
df=pd.DataFrame(data)
print(df)