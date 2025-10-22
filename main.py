import keyboard
import os
import warnings
import time
warnings.filterwarnings("ignore")
cwd = os.getcwd()

from Juliet_Dataset_Model.analyze_code import analyze_c_code

def get_all_subFolders(directory_path):
    subfiles = {}
    for root, dirs, files in os.walk(directory_path):
        for fileNames in files:
                full_path = os.path.join(root, fileNames)
                subfiles[fileNames] = full_path
    return subfiles

def is_c_or_cpp_file(filename):
        valid_extensions = ['.c', '.cpp']
        return any(filename.lower().endswith(ext) for ext in valid_extensions)

def main():
        filename = input("Put in file Name:")
        all_subFolders = get_all_subFolders(cwd)
        # print(all_subFolders)
        
        file_discovered_flag = False
        old_file_content = None
                
        while True:
                #Terminate Session
                if keyboard.is_pressed('Ctrl + C'):
                        print("Loop terminated by user.")
                        break
                
                if filename in all_subFolders.keys():
                        if not is_c_or_cpp_file(filename):
                                print(f"Error: '{filename}' is not a C or C++ file.")
                                print("Supported extensions: .c, .cpp, .cc, .cxx, .h, .hpp")
                                filename = input("Please enter a C or C++ file name:")
                                continue
                        
                        if not file_discovered_flag:
                                print("File Found")
                                file_discovered_flag = True
                        
                        #read the file the user wants to review
                        with open(all_subFolders[filename]) as f:
                                file_content = f.read()
                                if file_content != old_file_content:
                                        os.system("cls")
                                        # Determine language based on file extension
                                        language = "C++" if filename.lower().endswith(('.cpp')) else "C"
                                        analyze_c_code(file_content, language)
                                        old_file_content = file_content
                else:
                        #If file is not found, inform user and prompt again
                        print("File not found. Please try again.")
                        filename = input("Put in file Name:")
                time.sleep(0.5) 
main()
