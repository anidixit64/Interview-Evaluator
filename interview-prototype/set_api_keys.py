import keyring
import getpass

# --- Keyring Constants ---
KEYRING_SERVICE_NAME_GEMINI = "InterviewBotPro_Gemini"
KEYRING_USERNAME_GEMINI = "gemini_api_key"

KEYRING_SERVICE_NAME_OPENAI = "InterviewBotPro_OpenAI"
KEYRING_USERNAME_OPENAI = "openai_api_key"

def set_key_in_keyring(service_name, username, prompt_message):
    """Prompts user for a password and stores it in the keyring."""
    print(f"\n--- Setting Key for {service_name} ---")
    print(f"Service Name: {service_name}")
    print(f"Username:     {username}")

    try:
        # Use getpass to hide the input
        password = getpass.getpass(prompt=f"{prompt_message} (input will be hidden): ")

        if password: # Only set if something was entered
            keyring.set_password(service_name, username, password)
            print(f"Successfully stored the key for {service_name} in your system keyring.")
        else:
            print(f"No input received. Key for {service_name} was not set or updated.")

    except Exception as e:
        print(f"An error occurred while trying to set the key for {service_name}: {e}")
        print("Please ensure keyring is installed and configured correctly.")

if __name__ == "__main__":
    print("This script will securely store your API keys in your system's keyring.")
    print("You will be prompted to enter each key separately.")

    # Set Gemini Key
    set_key_in_keyring(
        KEYRING_SERVICE_NAME_GEMINI,
        KEYRING_USERNAME_GEMINI,
        "Enter your Gemini API Key"
    )

    # Set OpenAI Key
    set_key_in_keyring(
        KEYRING_SERVICE_NAME_OPENAI,
        KEYRING_USERNAME_OPENAI,
        "Enter your OpenAI API Key"
    )

    print("\n--- Keyring setup process finished. ---")