import os
import sys
from typing import List, Tuple
import openai
from dotenv import load_dotenv

def analyze_and_fix_file_with_llm(file_path: str) -> List[Tuple[int, str]]:
    """
    Анализирует файл на ошибки с сохранением отступов и номеров строк.
    
    Args:
        file_path (str): Путь к файлу
        
    Returns:
        List[Tuple[int, str]]: Список ошибок в формате (номер_строки, описание_ошибки)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Формируем код с номерами строк и сохраняем отступы
        code_with_line_numbers = ""
        for i, line in enumerate(lines, 1):
            # Сохраняем оригинальные отступы (пробелы или табуляцию)
            code_with_line_numbers += f"{i}: {line}"
        
        client = openai.OpenAI(
                api_key= os.getenv('TOKEN_LLM'), 
                base_url= os.getenv('URL_LLM'), 
            )
        
        response = client.chat.completions.create(
            model=os.getenv('MODEL_LLM',''),
            messages=[
                {
                    "role": "system",
                    "content": "Ты эксперт по Python. Проанализируй следующий код на наличие синтаксических и логических ошибок. Код содержит номера строк в начале каждой строки (например, '1: print(\"hello\")'). Возвращай только список ошибок в формате: номер_строки: описание_ошибки. Важно: сохраняй оригинальные отступы при анализе и исправлении."
                },
                {
                    "role": "user",
                    "content": f"Проанализируй этот Python код на ошибки:\n\n{code_with_line_numbers}"
                }
            ],
            temperature=0.1
        )
        
        llm_response = response.choices[0].message.content
        
        errors = []
        for line in llm_response.split('\n'):
            if ':' in line and not line.strip().startswith('#') and line.strip():
                try:
                    parts = line.split(':', 1)
                    line_num = int(parts[0].strip())
                    error_msg = parts[1].strip()
                    errors.append((line_num, error_msg))
                except (ValueError, IndexError):
                    continue
        
        return errors
        
    except Exception as e:
        return [(1, f"Ошибка при анализе кода: {str(e)}")]

def get_fix_suggestions(file_path: str, errors: List[Tuple[int, str]]) -> List[Tuple[int, str]]:
    """
    Получает предложения по исправлению ошибок от LLM с сохранением отступов.
    
    Args:
        file_path (str): Путь к файлу
        errors (List[Tuple[int, str]]): Список ошибок
        
    Returns:
        List[Tuple[int, str]]: Список предложений по исправлению в формате (номер_строки, исправленная_строка)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Формируем код с номерами строк и сохраняем отступы
        code_with_line_numbers = ""
        for i, line in enumerate(lines, 1):
            code_with_line_numbers += f"{i}: {line}"
        
        client = openai.OpenAI(
                api_key= os.getenv('TOKEN_LLM'), 
                base_url= os.getenv('URL_LLM'), 
            )
        
        error_details = "\n".join([f"Строка {line}: {msg}" for line, msg in errors])
        
        response = client.chat.completions.create(
            model=os.getenv('MODEL_LLM',''),
            messages=[
                {
                    "role": "system",
                    "content": "Ты эксперт по Python. Проанализируй код и предложи точные исправления для каждой ошибки. Код содержит номера строк в начале каждой строки (например, '1: print(\"hello\")'). Важно: при формировании исправленного кода сохраняй оригинальные отступы и структуру кода. Возвращай только исправленный код в формате: номер_строки: исправленная_строка"
                },
                {
                    "role": "user",
                    "content": f"Исправь следующий Python код:\n\n{code_with_line_numbers}\n\nОшибки:\n{error_details}"
                }
            ],
            temperature=0.1
        )
        
        llm_response = response.choices[0].message.content
        
        fixes = []
        for line in llm_response.split('\n'):
            if ':' in line and not line.strip().startswith('#') and line.strip():
                try:
                    parts = line.split(':', 1)
                    line_num = int(parts[0].strip())
                    fixed_code = parts[1].strip()
                    fixes.append((line_num, fixed_code))
                except (ValueError, IndexError):
                    continue
        
        return fixes
        
    except Exception as e:
        return [(1, f"Ошибка получения предложений по исправлению: {str(e)}")]

def fix_file_errors(file_path: str, errors: List[Tuple[int, str]]) -> bool:
    """
    Применяет исправления к файлу с сохранением отступов.
    
    Args:
        file_path (str): Путь к файлу
        errors (List[Tuple[int, str]]): Список ошибок для исправления
        
    Returns:
        bool: True если файл был изменен, False если нет
    """
    try:
        # Читаем исходный файл
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Получаем предложения по исправлению
        fixes = get_fix_suggestions(file_path, errors)
        
        if not fixes:
            return False
            
        # Применяем исправления
        modified = False
        for line_num, fixed_code in fixes:
            if 1 <= line_num <= len(lines):
                # Сохраняем оригинальные отступы из исходной строки
                original_line = lines[line_num - 1]
                
                # Определяем количество ведущих пробелов (или табуляций)
                leading_spaces = len(original_line) - len(original_line.lstrip())
                
                # Создаем новую строку с сохранением отступов
                new_line = ' ' * leading_spaces + fixed_code + '\n'
                
                # Заменяем строку в массиве
                lines[line_num - 1] = new_line
                modified = True
        
        if modified:
            # Записываем обратно в файл
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
        
        return modified
        
    except Exception as e:
        print(f"Ошибка при применении исправлений: {str(e)}")
        return False

def main():
    if os.path.exists('.env'):
        load_dotenv('.env')
    file_path = '/home/lifeteo/LLM/AI_Advent_2025/llm17/llm15.py'
    
    # Проверяем существование файла
    if not os.path.exists(file_path):
        print(f"Файл {file_path} не найден")
        sys.exit(1)
    
    errors = analyze_and_fix_file_with_llm(file_path)
    
    if errors:
        print("Найдены ошибки:")
        for line_num, error_msg in errors:
            print(f"Ошибка в строке {line_num}: {error_msg}")
        
        # Применяем исправления
        if fix_file_errors(file_path, errors):
            print("Исправления применены к файлу")
        else:
            print("Исправления не были применены")
    else:
        print("Ошибок в коде не найдено")

if __name__ == "__main__":
    main()
