import os

# Keep the test suite deterministic even when local development uses real providers.
os.environ["ENVIRONMENT"] = "test"
os.environ["LLM_PROVIDER"] = "fake"
os.environ["EMBEDDING_PROVIDER"] = "fake"
os.environ["LLM_API_KEY"] = ""
os.environ["GROQ_API_KEY"] = ""
os.environ["EMBEDDING_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
