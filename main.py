import keyboard
import os
import time
cwd = os.getcwd()


def get_all_subFolders(directory_path):
    subfiles = []
    for root, dirs, files in os.walk(directory_path):
        for fileNames in files:
                subfiles.append(fileNames)
    return subfiles

def main():
        filename = input("Put in file Name:")
        all_subFolders = get_all_subFolders(cwd)
        
        file_discovered_flag = False
        old_file_content = None
                
        while True:
                #Terminate Session
                if keyboard.is_pressed('Ctrl + C'):
                        print("Loop terminated by user.")
                        break
                
                if filename in all_subFolders:
                        #inform the user the file has been found only once using the flag
                        if not file_discovered_flag:
                                print("File Found")
                                file_discovered_flag = True
                        
                        #read the file the user wants to review
                        with open(filename) as f:
                                file_content = f.read()
                                #checks for any changes made to the file(This method forces user to save for changes to be recognized)
                                if file_content != old_file_content:
                                        security_checker(file_content)
                                        print(file_content)
                                old_file_content = file_content
                else:
                        #If file is not found, inform user and prompt again
                        print("File not found. Please try again.")
                        filename = input("Put in file Name:")
                
                
def security_checker(file_content):        
        pass
main()