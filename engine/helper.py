import re

from engine.config import ASSISTANT_NAME


def extract_yt_term(command):
    # Define a regular expression pattern to capture the song name
    pattern = r'play\s+(.*?)\s+on\s+youtube'
    #Use re.search to find the match in the command
    match = re.search(pattern, command, re.IGNORECASE)
    # If a match is found, return the extracted song name;
    return match.group(1) if match else None

def remove_words(input_string, words_to_remove):
    # split the input string into words
    words=input_string.split()
        # Remove unwanted words
    filtered_words = [word for word in words if word.lower() not in words_to_remove]
    #  Join the remainingwords back into a string
    result_string =' '.join(filtered_words)
    return result_string

# # Example usage
# input_string = "make a phone call to shreya"
# words_to_remove=[ASSISTANT_NAME, 'make', 'a', 'to', 'phone', 'call', 'send', 'message', 'whatsapp', '']
# results= remove_words(input_string, words_to_remove)
# print(results)