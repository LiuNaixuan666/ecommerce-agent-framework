import os

def create_project_structure():
    # 定义项目根目录名称
    project_name = "ecommerce-agent-framework"
    
    # 定义目录树结构
    # 键是文件夹路径，值是该文件夹下需要初始化的文件列表
    structure = {
        f"{project_name}/app": ["__init__.py", "main.py", "config.py", "engine.py"],
        f"{project_name}/app/api": ["__init__.py", "routes_chat.py", "routes_knowledge.py", "routes_evaluation.py"],
        f"{project_name}/app/agent": ["__init__.py", "workflow.py", "intent_parser.py", "clarification.py", "uncertainty_detector.py", "response_generator.py"],
        f"{project_name}/app/rag": ["__init__.py", "retriever.py", "vector_store.py", "embedder.py", "reranker.py"],
        f"{project_name}/app/knowledge": ["__init__.py", "ingestion.py", "document_parser.py", "chunking.py", "merchant_manager.py"],
        f"{project_name}/app/models": ["__init__.py", "schemas.py", "merchant.py"],
        f"{project_name}/data/merchants": [".gitkeep"], # 保持空目录不被git忽略
        f"{project_name}/data/evaluation_sets": [".gitkeep"],
        f"{project_name}/experiments": ["test_questions.json", "run_llm_only.py", "run_rag.py", "run_agent_rag.py", "evaluation_metrics.py"],
        f"{project_name}/docs": ["architecture.png", "methodology_notes.md"],
    }

    # 根目录下额外需要的文件
    root_files = [".env", "requirements.txt", "README.md", ".gitignore"]

    print(f"🚀 开始创建项目: {project_name}")

    # 创建文件夹和文件
    for path, files in structure.items():
        os.makedirs(path, exist_ok=True)
        for file in files:
            file_path = os.path.join(path, file)
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    if file.endswith('.py'):
                        f.write(f'# {file}\n')
                print(f"  ✅ 已创建文件: {file_path}")

    # 创建根目录文件
    for file in root_files:
        file_path = os.path.join(project_name, file)
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as f:
                if file == ".gitignore":
                    f.write("__pycache__/\n.env\nvenv/\n*.db\ndata/merchants/*\n!data/merchants/.gitkeep")
                elif file == "requirements.txt":
                    f.write("fastapi\nuvicorn\nlangchain\nopenai\nchromadb\npython-docx\npypdf\npandas\npython-dotenv")
            print(f"  ✅ 已创建根目录文件: {file_path}")

    print("\n🎉 项目骨架已搭建完成！")
    print(f"💡 建议下一步：cd {project_name} && pip install -r requirements.txt")

if __name__ == "__main__":
    create_project_structure()