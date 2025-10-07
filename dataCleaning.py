import pandas as pd
##Hugging Face Dataset
df = pd.read_json("https://huggingface.co/datasets/CyberNative/Code_Vulnerability_Security_DPO/resolve/main/secure_programming_dpo.json", lines=True)
# df.to_csv("Datasets/init_HuggingFace.csv", index=False)
clean_df = df

clean_df.drop_duplicates(keep='last', inplace=True)
clean_df = clean_df[clean_df["lang"] == "c++"]

clean_df.to_csv("Datasets/Clean_HuggingFace.csv", index=False)