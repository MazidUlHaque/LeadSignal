"""Concept lexicon v1.0.

Derived from the 50-concept TKAED lexicon, with keyword lists rewritten for
bibliometric matching:
  * single ambiguous words ("tree", "class", "image", "prompt", "reward",
    "pipeline", "React") were replaced by multi-word phrases or guarded by
    exclusion terms;
  * each alias belongs to exactly one concept (for example "BERT" is only
    counted under transformer architectures);
  * short all-capital acronyms (LLM, RAG, NLP, ...) are matched case-sensitively,
    everything else case-insensitively (see match.py).

Volatility classes are hypotheses to be tested (H1b), not facts.
GitHub topics are best guesses and must be confirmed in the pilot.

Frozen for the pre-enrollment phase. Any change creates a new version with a
dated changelog entry (see CHANGELOG below).
"""

from __future__ import annotations

import json
from typing import Dict, List

LEXICON_VERSION = "1.0"

CHANGELOG: List[Dict[str, str]] = [
    {"version": "1.0", "date": "2026-09-25",
     "change": "Initial LeadSignal-CS lexicon derived from TKAED; keywords rewritten for matching."},
]


def _c(label, volatility, area, aliases, exclude=None, topic=None):
    return {
        "label": label,
        "volatility": volatility,
        "area": area,
        "aliases": list(aliases),
        "exclude": list(exclude or []),
        "github_topic": topic,
    }


LEXICON: Dict[str, Dict] = {
    # ------------------------------------------------------------ stable (15)
    "algorithms": _c("Algorithms", "stable", "theory",
        ["approximation algorithm", "graph algorithm", "sorting algorithm",
         "dynamic programming", "randomized algorithm", "online algorithm",
         "algorithm design"], topic="algorithms"),
    "data_structures": _c("Data Structures", "stable", "theory",
        ["data structure", "hash table", "linked list", "binary search tree",
         "priority queue", "succinct data structure"], topic="data-structures"),
    "computational_complexity": _c("Computational Complexity", "stable", "theory",
        ["computational complexity", "NP-hard", "NP-complete", "complexity class",
         "time complexity", "space complexity", "hardness of approximation"]),
    "discrete_mathematics": _c("Discrete Mathematics", "stable", "mathematics",
        ["discrete mathematics", "combinatorics", "graph theory",
         "extremal combinatorics", "enumerative combinatorics"]),
    "formal_languages": _c("Formal Languages and Automata", "stable", "theory",
        ["automaton", "automata", "regular expression", "context-free grammar",
         "formal language", "Turing machine", "pushdown automaton"], topic="automata"),
    "computer_architecture": _c("Computer Architecture", "stable", "systems",
        ["computer architecture", "microarchitecture", "memory hierarchy",
         "instruction set architecture", "cache coherence", "branch prediction"],
        topic="computer-architecture"),
    "operating_systems": _c("Operating Systems", "stable", "systems",
        ["operating system", "OS kernel", "process scheduling", "virtual memory",
         "file system", "system call"], topic="operating-system"),
    "networking_fundamentals": _c("Networking Fundamentals", "stable", "systems",
        ["TCP/IP", "network protocol", "congestion control", "routing protocol",
         "software-defined networking", "transport protocol"], topic="networking"),
    "database_theory": _c("Database Theory", "stable", "systems",
        ["relational database", "query optimization", "query optimisation",
         "transaction processing", "relational algebra", "database system"],
        topic="database"),
    "software_engineering": _c("Software Engineering", "stable", "engineering",
        ["software engineering", "software design", "design pattern",
         "code review", "software testing", "refactoring", "software maintenance"],
        topic="software-engineering"),
    "object_oriented_programming": _c("Object-Oriented Programming", "stable", "programming",
        ["object-oriented", "object oriented programming", "inheritance hierarchy",
         "subtype polymorphism"], topic="oop"),
    "functional_programming": _c("Functional Programming", "stable", "programming",
        ["functional programming", "higher-order function", "lambda calculus",
         "Haskell", "purely functional"], topic="functional-programming"),
    "compiler_design": _c("Compiler Design", "stable", "systems",
        ["compiler", "compiler optimization", "compiler optimisation",
         "intermediate representation", "register allocation"], topic="compiler"),
    "linear_algebra": _c("Linear Algebra", "stable", "mathematics",
        ["linear algebra", "eigenvalue", "singular value decomposition",
         "matrix factorization", "matrix factorisation", "low-rank approximation"],
        topic="linear-algebra"),
    "probability_statistics": _c("Probability and Statistics", "stable", "mathematics",
        ["probability theory", "statistical inference", "hypothesis testing",
         "Bayesian inference", "stochastic process"], topic="statistics"),

    # ---------------------------------------------------------- moderate (20)
    "machine_learning": _c("Machine Learning Fundamentals", "moderate", "ai_ml",
        ["machine learning", "supervised learning", "unsupervised learning",
         "gradient descent", "feature engineering"], topic="machine-learning"),
    "deep_learning": _c("Deep Learning", "moderate", "ai_ml",
        ["deep learning", "deep neural network", "convolutional neural network",
         "recurrent neural network", "backpropagation", "LSTM"], topic="deep-learning"),
    "natural_language_processing": _c("Natural Language Processing", "moderate", "ai_ml",
        ["natural language processing", "NLP", "named entity recognition",
         "sentiment analysis", "machine translation", "text classification"], topic="nlp"),
    "computer_vision": _c("Computer Vision", "moderate", "ai_ml",
        ["computer vision", "image classification", "object detection",
         "semantic segmentation", "image segmentation"], topic="computer-vision"),
    "cloud_computing": _c("Cloud Computing", "moderate", "systems",
        ["cloud computing", "serverless", "infrastructure as a service",
         "platform as a service", "cloud service"], topic="cloud-computing"),
    "devops": _c("DevOps", "moderate", "engineering",
        ["DevOps", "continuous integration", "continuous deployment",
         "continuous delivery", "infrastructure as code", "CI/CD"], topic="devops"),
    "agile_methodologies": _c("Agile Methodologies", "moderate", "engineering",
        ["agile software development", "agile development", "Scrum", "Kanban",
         "agile method", "user story"], topic="agile"),
    "microservices": _c("Microservices", "moderate", "engineering",
        ["microservice", "service mesh", "API gateway", "service-oriented architecture"],
        topic="microservices"),
    "containerisation": _c("Containerisation", "moderate", "systems",
        ["containerization", "containerisation", "container virtualization",
         "Linux container", "container runtime"], topic="containers"),
    "cybersecurity": _c("Cybersecurity Fundamentals", "moderate", "security",
        ["cybersecurity", "cyber security", "penetration testing",
         "intrusion detection", "malware detection", "network security"],
        topic="cybersecurity"),
    "data_engineering": _c("Data Engineering", "moderate", "data",
        ["data pipeline", "ETL", "data warehouse", "data lake", "Apache Spark",
         "Apache Kafka", "stream processing"], topic="data-engineering"),
    "nosql_databases": _c("NoSQL Databases", "moderate", "data",
        ["NoSQL", "MongoDB", "Cassandra", "key-value store", "document database",
         "document store"], topic="nosql"),
    "api_design": _c("API Design", "moderate", "engineering",
        ["REST API", "RESTful", "GraphQL", "gRPC", "OpenAPI", "API design"],
        topic="rest-api"),
    "parallel_computing": _c("Parallel Computing", "moderate", "systems",
        ["parallel computing", "GPU programming", "CUDA", "OpenMP", "MPI",
         "parallel algorithm"], topic="parallel-computing"),
    "distributed_systems": _c("Distributed Systems", "moderate", "systems",
        ["distributed system", "consensus protocol", "Byzantine fault",
         "Paxos", "Raft consensus", "CAP theorem"], topic="distributed-systems"),
    "reinforcement_learning": _c("Reinforcement Learning", "moderate", "ai_ml",
        ["reinforcement learning", "Q-learning", "policy gradient",
         "Markov decision process", "actor-critic"], topic="reinforcement-learning"),
    "explainable_ai": _c("Explainable AI", "moderate", "ai_ml",
        ["explainable AI", "explainable artificial intelligence", "XAI", "SHAP",
         "model interpretability", "feature attribution"], topic="explainable-ai"),
    "graph_neural_networks": _c("Graph Neural Networks", "moderate", "ai_ml",
        ["graph neural network", "GNN", "graph convolutional network", "GCN",
         "message passing neural network"], topic="graph-neural-networks"),
    "quantum_computing": _c("Quantum Computing", "moderate", "theory",
        ["quantum computing", "quantum algorithm", "qubit", "quantum circuit",
         "quantum machine learning"], topic="quantum-computing"),
    "ai_ethics": _c("Ethics in AI", "moderate", "ai_ml",
        ["AI ethics", "algorithmic fairness", "responsible AI", "AI fairness",
         "algorithmic bias", "ethical AI"], topic="ai-ethics"),

    # ---------------------------------------------------------- volatile (15)
    "tensorflow": _c("TensorFlow", "volatile", "ai_ml_tools",
        ["TensorFlow", "Keras"], topic="tensorflow"),
    "pytorch": _c("PyTorch", "volatile", "ai_ml_tools",
        ["PyTorch", "PyTorch Lightning", "TorchScript"], topic="pytorch"),
    "kubernetes": _c("Kubernetes", "volatile", "systems_tools",
        ["Kubernetes", "K8s", "container orchestration", "Helm chart", "kubectl"],
        topic="kubernetes"),
    "docker": _c("Docker", "volatile", "systems_tools",
        ["Docker", "Dockerfile", "Docker Compose"], topic="docker"),
    "react_framework": _c("React Framework", "volatile", "web_tools",
        ["ReactJS", "React.js", "React Native", "Next.js", "JSX"],
        exclude=["ReAct prompting", "ReAct agent"], topic="react"),
    "large_language_models": _c("Large Language Models", "volatile", "ai_ml",
        ["large language model", "LLM", "foundation model", "GPT-3", "GPT-4",
         "ChatGPT", "instruction tuning"], topic="llm"),
    "transformer_architectures": _c("Transformer Architectures", "volatile", "ai_ml",
        ["transformer", "self-attention", "multi-head attention",
         "vision transformer", "BERT"],
        exclude=["power transformer", "electrical transformer", "transformer substation"],
        topic="transformers"),
    "prompt_engineering": _c("Prompt Engineering", "volatile", "ai_ml",
        ["prompt engineering", "chain-of-thought", "in-context learning",
         "few-shot prompting", "prompt tuning"], topic="prompt-engineering"),
    "aws_services": _c("AWS Services", "volatile", "cloud_tools",
        ["Amazon Web Services", "AWS", "Amazon EC2", "Amazon S3", "AWS Lambda",
         "SageMaker"], topic="aws"),
    "mlops": _c("MLOps", "volatile", "ai_ml_tools",
        ["MLOps", "machine learning operations", "model deployment",
         "model monitoring", "feature store", "MLflow"], topic="mlops"),
    "vector_databases": _c("Vector Databases", "volatile", "data",
        ["vector database", "vector search", "approximate nearest neighbor search",
         "FAISS", "vector store"], topic="vector-database"),
    "retrieval_augmented_generation": _c("Retrieval-Augmented Generation", "volatile", "ai_ml",
        ["retrieval-augmented generation", "retrieval augmented generation", "RAG"],
        topic="rag"),
    "diffusion_models": _c("Diffusion Models", "volatile", "ai_ml",
        ["diffusion model", "denoising diffusion", "stable diffusion", "DDPM",
         "score-based generative model"],
        exclude=["information diffusion", "diffusion process on networks"],
        topic="diffusion-models"),
    "edge_computing": _c("Edge Computing", "volatile", "systems",
        ["edge computing", "edge AI", "fog computing", "TinyML",
         "mobile edge computing"], topic="edge-computing"),
    "federated_learning": _c("Federated Learning", "volatile", "ai_ml",
        ["federated learning", "federated averaging", "federated optimization"],
        topic="federated-learning"),
}


def validate(lexicon: Dict[str, Dict] = None) -> List[str]:
    """Return a list of problems; empty means the lexicon is consistent."""
    lexicon = lexicon or LEXICON
    problems: List[str] = []
    seen: Dict[str, str] = {}
    for cid, c in lexicon.items():
        if c["volatility"] not in {"stable", "moderate", "volatile"}:
            problems.append(f"{cid}: unknown volatility {c['volatility']!r}")
        if not c["aliases"]:
            problems.append(f"{cid}: no aliases")
        for a in c["aliases"]:
            key = a.lower()
            if key in seen and seen[key] != cid:
                problems.append(f"alias {a!r} used by both {seen[key]} and {cid}")
            seen[key] = cid
    return problems


def counts_by_class(lexicon: Dict[str, Dict] = None) -> Dict[str, int]:
    lexicon = lexicon or LEXICON
    out: Dict[str, int] = {}
    for c in lexicon.values():
        out[c["volatility"]] = out.get(c["volatility"], 0) + 1
    return out


def to_json(lexicon: Dict[str, Dict] = None) -> str:
    return json.dumps({"version": LEXICON_VERSION, "changelog": CHANGELOG,
                       "concepts": lexicon or LEXICON}, indent=2)
