import os
import sys
from typing import List, Tuple
import openai
from dotenv import load_dotenv
import re

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
            code_with_line_numbers += f"{i}: {clean(line)}"
        
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

def get_fix_suggestions(file_path: str, errors: List[Tuple[int, str]]) -> List[Tuple[int, str, str]]:
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
            code_with_line_numbers += f"{i}: {clean(line)}"
        
        client = openai.OpenAI(
                api_key= os.getenv('TOKEN_LLM'), 
                base_url= os.getenv('URL_LLM'), 
            )
        
        error_details = "\n".join([f"Строка {line}: {msg}" for line, msg in errors])
        code_with_line_numbers = clean(code_with_line_numbers)
        response = client.chat.completions.create(
            model=os.getenv('MODEL_LLM',''),
            messages=[
                {
                    "role": "system",
                    "content": "Ты эксперт по Python. Проанализируй код и предложи точные исправления для каждой ошибки. Код содержит номера строк в начале каждой строки (например, '1: print(\"hello\")'). Важно: при формировании исправленного кода сохраняй оригинальные отступы и структуру кода. ВОЗВРАЩАЙ только исправленный код в формате, каждый набор с новой строки : номер_строки, действие (заменить, добавить), исправленная_строка"
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
            try:
                parts = line.split(',', 2)
                line_num = int(parts[0].strip())
                action_code = parts[1].strip()
                fixed_code = parts[2].strip()
                fixes.append((line_num, action_code, fixed_code))
            except (ValueError, IndexError):
                continue
        for fix in fixes:
            print(fix)
        return fixes
        
    except Exception as e:
        return [(1, '', f"Ошибка получения предложений по исправлению: {str(e)}")]

def fix_file_errors(file_path: str, errors: List[Tuple[int, str, str]]) -> bool:
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
            linelines = f.readlines()
        
        # Получаем предложения по исправлению
        fixes = get_fix_suggestions(file_path, errors)
        
        if not fixes:
            return False
            
        # Применяем исправления
        modified = False
        original_line = ''
        new_file = []
        pre_line = ''
        
        for inx_line, line in enumerate(linelines):
            
            original_line = line
            found_items = [item for item in fixes if item[0] == inx_line+1]
            if found_items:
                ind, action_code, fixed_code = found_items[0]
                
                # Определяем количество ведущих пробелов (или табуляций)
                leading_spaces = len(original_line) - len(original_line.lstrip())
                
                if action_code == 'заменить':
                    # Создаем новую строку с сохранением отступов
                    new_line = ' ' * leading_spaces + fixed_code + '\n'
                    # Заменяем строку в массиве
                    new_file.append(new_line)
                    modified = True
                elif action_code == 'добавить':
                    # Создаем новую строку с сохранением отступов
                    new_line = ' ' * leading_spaces + fixed_code + '\n'
                    
                    new_file.append(new_line)
                    new_file.append(pre_line)
                    modified = True
                else:
                    new_file.append(fixed_code)
                    pre_line = original_line
            else:
                pre_line = original_line
                new_file.append(original_line)
            
        # for line_num, action_code, fixed_code in fixes:
        #     if 2 <= line_num <= len(lines):
        #         # Сохраняем оригинальные отступы из исходной строки
        #         original_line = lines[line_num - 1]
                
        #         # Определяем количество ведущих пробелов (или табуляций)
        #         leading_spaces = len(original_line) - len(original_line.lstrip())
                
        #         if action_code == 'заменить':
        #             # Создаем новую строку с сохранением отступов
        #             new_line = ' ' * leading_spaces + fixed_code + '\n'
                    
        #             # Заменяем строку в массиве
        #             new_file.append(new_line)
        #             modified = True
        #         elif action_code == 'добавить':
        #             # Создаем новую строку с сохранением отступов
        #             new_line = ' ' * leading_spaces + fixed_code + '\n'
                    
        #             new_file.append(new_line)
        #             new_file.append(pre_line)
        #             modified = True
        #         else:
        #             new_file.append(original_line)
        #         pre_line = original_line
                
        
        if modified:
            # Записываем обратно в файл
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(new_file)
        
        return modified
        
    except Exception as e:
        print(f"Ошибка при применении исправлений: {str(e)}")
        return False

def clean(prompt):
    # Удаление лишних пробелов и переносов строк
    prompt = re.sub(r'\s+', ' ', prompt)
    # Удаление комментариев
    prompt = re.sub(r'#.*', '', prompt)
    return prompt

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
