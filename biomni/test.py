from biomni.agent import A1

# Initialize the agent with data path, Data lake will be automatically downloaded on first run (~11GB)
agent = A1(llm="gpt-5-mini", expected_data_lake_files=[])
QUESTIONS = [
    "Is YES1 amplified as ecDNA or BFB in CCLE? In which samples?",
    "Summarize the size distribution of all BFB amplifications (Captured interval length)",
    "List all BFB amplifications in HARA (feature IDs, loci, genes, copy number)",
    "Which oncogenes are most frequently amplified as BFB? (top 25)",
    "Show the distribution of amplification classes across cancer types (Tissue of origin)",
    "For each tissue, what fraction of samples have any ecDNA?",
    "Do Complexity scores differ between ecDNA vs BFB vs Linear vs Complex-non-cyclic?",
    "For ecDNA vs BFB, how does size relate to max copy number? (scatter + correlation)",
    "What are the highest copy-number amplifications in CCLE? (top 5)",
    "Which oncogenes appear in both ecDNA and BFB across CCLE?",
    "Which samples contain both ecDNA and BFB amplifications?",
    "Are ecDNA amplifications larger than BFB on average?",
    "Which samples have high-copy (>20 CN) ecDNA?",
    "What is the largest amplicon (by size) per class?",
    "Which tissues show highest amplification complexity (median)?",
    "For a given gene EGFR, list all co-amplified genes (same feature)",
    "Which oncogenes are exclusive to ecDNA?",
    "Which chromosomes are most frequently amplified?",
    "Which oncogenes are most recurrent across unique samples (any class)?",
    "For each tissue, what are the top 5 amplified oncogenes (any class, by #unique samples)?",
    "Which tissues have the highest fraction of BFB features?",
    "Among samples with ecDNA, what are the most common co-amplified oncogene pairs?",
    "Which samples have amplifications on multiple chromosomes? (by feature loci)",
    "For each class, what is the distribution of number of oncogenes per feature?",
]
# Execute biomedical tasks using natural language
# Execute biomedical tasks using natural language
# agent.go("For aa given gene EGFR, list all co-amplified genes (same feature) in the CCLE data.")
# agent.go("Is NCBI gen ID NR_119377 amplified as ecDNA or BFB in CCLE? In which samples? Use the amplicon_table tool and CCLE.csv. Be efficient.")
# agent.go("Is YES1 amplified as ecDNA or BFB in CCLE? In which samples? ")
# agent.go("in CCLE dataset, show me all cases that are Heavily rearranged unichromosomal amplifications. return the sample name and amplicon number and feature number. ")
agent.go("In the CCLE dataset, find all samples that contain a foldback structural variant (SV) on chromosome 9 with breakpoints at chr9:105054355 and chr9:105055066(within the window of 50k bp). Return the following fields for each matching event: sample_name, amplicon_number, feature_number.")
# agent.go("For ecDNA vs BFB, how does size relate to max copy number? (scatter + correlation) at CCLE data")
# agent.go("return all samples in breast cancer containign BFB. tell me In which samples? Use the amplicon_table tool and CCLE.csv. Be efficient.")
# agent.go("show me all BFBs in CCLE at breast cancer samples using amplicon_table and CCLE.csv")
# agent.go("Among samples with ecDNA, what are the most common co-amplified oncogene pairs?")

# for idx, question in enumerate(QUESTIONS, start=1):
#     print(f"\n=== QUESTION {idx} ===")
#     agent.go(question)
