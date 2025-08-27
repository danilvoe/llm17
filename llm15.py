# Запрос на создание кода
# Когда создаст нужно сохранить его в файл
# После этого нужно написать тесты
# Сохранить в файл
# Запустить тесты
# Вывести результат

import ollama #qwen3-coder:30b
import json
import re
import os
from dotenv import load_dotenv
import docker
import git
import requests

class BasicActionLLM:
    def __init__(self):
        self.model = ""
        self.conversation_history = []
        self.system_prompt = """
            1. ответай и рассуждай только на Русском языке.
            2. Отвечай только фактом, без "я думаю", "можно сказать" и других рассуждений.
            3. не придумывай
            4. Ты эксперт по Python, LLM и ollama 
        """
        self.finish_prompt = ""
        self.think_delete = False

    def add_to_context(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})

    def clear_context(self):
        self.conversation_history = []

    def get_llm_response(self, prompt: str, role='user'):
        final_response = False
        self.add_to_context(role, prompt)
        try:
            client = ollama.Client(host=os.getenv('HOST_PORT_OLLAMA'))
            response = client.chat(
                model=os.getenv('OLLAMA_MODEL'),
                messages=self.conversation_history,
                stream=False,                
            )
            return response
        except Exception as e:
            print(f"Ошибка при обращении к LLM: {str(e)}")
            return final_response, ""

    def clean_response(self, llm_response: str):
        return re.sub(r"<think>.*?</think>", "", llm_response, flags=re.DOTALL).strip()

class CodeWriteCodeCheck():
    def __init__(self):
        self.ai = BasicActionLLM()
    
    def start_dialog(self):
        print('Генерирую конесколько классов и в них по 3-5 методов')
        promt = "создай несколько классов и в них по 3-5 методов на Python. классы должны быть связаны между собой и иметь некую полезную работу. Нужен только, код без объяснений!!!!"
        result = self.ai.get_llm_response(promt)
        self.ai.add_to_context("assistant", result.message.content)
        code = re.sub(r'^```python\s*|\s*```$', '', result.message.content, flags=re.MULTILINE)
        code = re.sub(r'^\s*```python\s*|\s*```\s*$', '', code, flags=re.MULTILINE)
        if os.path.exists('code_from_test.py'):
            os.remove("code_from_test.py")
        with open("code_from_test.py", "w") as file:
            file.write(code)
        print('Формирую тесты для полученного кода')
        promt = '''
        1. напиши unit тесты к коду c использованием unittest. 
        2. не забудь импорты от классов кода который будет проверятся! 
        3. сделай импорт code_from_test и всех классов
        4. НЕ вставлях исходный код классов которые необходимо проверить
        5. Убедись что все импорты правильно указаны!
        6. Проверь корректность тестов
        7. тесты должны сами запускаться при выполнении файла'''
        result = self.ai.get_llm_response(promt)
        test_code = re.sub(r'^```python\s*|\s*```$', '', result.message.content, flags=re.MULTILINE)
        #test_code = re.sub(r'^\s*```python\s*|\s*```\s*$', '', test_code, flags=re.MULTILINE)
        print('Получил тесты, записываю в файл')
        if os.path.exists('test_code.py'):
            os.remove("test_code.py")
        with open("test_code.py", "w") as file:
            file.write(test_code)
        print('Запускаю тесты')
        doc = DockerRun()
        result_run_text, error_run_test = doc.run_file_python("test_code.py")
        print(result_run_text)
        if error_run_test:
            print('Исправляю тесты, записываю в файл')
            promt = f"Исправь юнит тесты! Ошибка: {result_run_text}"
            self.ai.add_to_context("assistant", result.message.content)
            result = self.ai.get_llm_response(promt)
            test_code = re.sub(r'^```python\s*|\s*```$', '', result.message.content, flags=re.MULTILINE)
            #test_code = re.sub(r'^\s*```python\s*|\s*```\s*$', '', test_code, flags=re.MULTILINE)
            if os.path.exists('test_code.py'):
                os.remove("test_code.py")
            with open("test_code.py", "w") as file:
                file.write(test_code)
            result_run_text, error_run_test = doc.run_file_python("test_code.py")
            print(result_run_text)
            if not error_run_test:
                print("Делаем коммит")
                Jobs.commit()
                print("Отправляем данные на GitHub")
                Jobs.push()
                print("Создаем релиз и тэг на GitHub")
                Jobs.release()
        else:
            print("Делаем коммит")
            Jobs.commit()
            print("Отправляем данные на GitHub")
            Jobs.push()
            print("Создаем релиз и тэг на GitHub")
            Jobs.release()

class DockerRun(BasicActionLLM):
    def __init__(self):
        self.model = os.getenv('OLLAMA_MODEL')
        self.conversation_history = []

        self.sending_prompt = ""
        self.think_delete = True
            
    @staticmethod
    def run_file_python(file_path:str):
        project_folder = '/home/lifeteo/LLM/AI_Advent_2025/llm15/'
        folder = '/project/'
        client = docker.from_env()
        try:
            result = client.containers.run(
                image ='python:3',
                command =f'python "{folder + file_path}"',
                volumes={
                    project_folder: {
                        'bind': folder,
                        'mode': 'rw'  # или 'ro' для read-only
                    }
                },
                remove=True,
                stderr=True,
                stdout=True
            )
        except Exception as e:
            return f"Ошибка выполнения тестов: {e.stderr.decode('utf-8')}", True
        return result.decode('utf-8'), False

class Jobs():
    
    def commit():
        repo = git.Repo('.')
        repo.git.add('.')
        repo.index.commit('Auto commit')

    def push():
        repo = git.Repo('.')
        origin = repo.remote('origin')
        origin.push()
        
    def release():
        url = "https://api.github.com/repos/danilvoe/llm15/releases"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        data = {
            "tag_name": "v1.0.0",
            "target_commitish": "main",
            "name": "v1.0.0",
            "body": '''
## Первый автоматический релиз на GitHub

**День 15 AI Advent 2025**

Это первый автоматически сгенерированный релиз проекта.  
В рамках события [AI Advent 2025](https://t.me/mobiledevnews/3707) был опубликован первый релиз.

### Что нового?

- Автоматическая сборка и публикация релиза
- Первая версия проекта
            ''',
            "draft": False,
            "prerelease": False,
            "generate_release_notes": False
        }

        response = requests.post(url, headers=headers, json=data)

def main():
    bot_info = BasicActionLLM()
    if os.path.exists('.env'):
        load_dotenv('.env')
    dialog = CodeWriteCodeCheck()
    print(dialog.start_dialog(), end='\n')

if __name__ == "__main__":
    main()