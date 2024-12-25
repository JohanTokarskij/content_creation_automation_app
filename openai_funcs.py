import json
import os
from typing import List, Dict, Optional

from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Initialize the OpenAI client
client = OpenAI(
    api_key=OPENAI_API_KEY
)

def call_openai_chat(
    prompt,
    model="gpt-4o",
    max_tokens=1600,
    temperature=0.7,
    functions=None,
    function_call=None,
):
    """
    Calls the OpenAI Chat API and supports structured outputs with functions.
    
    Args:
        prompt (str): The input prompt to the model.
        model (str): The model name to use.
        max_tokens (int): The maximum tokens for the response.
        temperature (float): Sampling temperature.
        functions (list): List of function definitions for structured output.
        function_call (dict): Optional function call specification.
    
    Returns:
        dict or str: Returns a structured response as a dictionary if functions are used, 
                     or a string for normal text completions.
    """
    try:
        # Build the base request
        request_payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        # Add function definitions if provided
        if functions:
            request_payload["functions"] = functions
        if function_call:
            request_payload["function_call"] = function_call

        # Make the API call
        response = client.chat.completions.create(**request_payload)
        
        # Check if the response includes a function call
        if functions:
            function_call_data = response.choices[0].message.function_call
            function_response = json.loads(function_call_data.arguments)
            return function_response
        
        # Return the text content for normal prompts
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"An error occurred during the OpenAI API call: {e}")
        return None


def generate_video_topic(subject_or_theme: str, previous_facts: Optional[List[str]] = None) -> str:
    """
    Generates a very specific, interesting, and lesser-known fact related to the given subject or theme.

    Args:
        subject_or_theme (str): The main subject or theme for generating the fact.
        previous_facts (Optional[List[str]]): A list of previously generated facts to avoid repetition.

    Returns:
        str: A single, concise fact related to the subject or "No new fact found."
    """
    if previous_facts is None:
        previous_facts = []
    previous_facts_text = "\n".join(f"- {fact}" for fact in previous_facts)

    prompt = f"""
    Generate a very specific, interesting, and lesser-known fact related to the following subject: "{subject_or_theme}".
    The fact should be engaging, surprising, and not commonly known. Provide the fact as a single, concise sentence.

    Important Instructions:
    - Do not repeat any of the following facts:
    {previous_facts_text}
    - Do not include any markdown formatting or code blocks.
    - Only return the fact as plain text.
    - Ensure the fact is fresh and unique.

    If you cannot find a new fact, respond with "No new fact found."

    """

    video_topic = call_openai_chat(prompt, temperature=0.9)

    print("\nGenerated Video Topic:")
    print(video_topic)
    print("\n")

    return video_topic


def generate_script(video_topic: str, video_duration_secs: int) -> List[str]:
    """
    Generates a structured script for a YouTube video based on the given topic.

    Args:
        video_topic (str): The topic of the video.

    Returns:
        list: A list of scenes as strings, each containing 1-2 sentences.
    """
    # Define the function schema for structured output
    function_definition = [
        {
            "name": "generate_scene_list",
            "description": f"Generates a structured list of scenes for a {video_duration_secs}-second video.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenes": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "description": "A single scene description containing 1-2 sentences.",
                        },
                    },
                },
                "required": ["scenes"],
            },
        }
    ]

    # Construct the prompt
    prompt = f"""
    You are an assistant that creates structured scripts for {video_duration_secs} seconds YouTube video based on a given topic. 
    The video should be divided into 3-4 scenes, each lasting about 5 seconds to fit the total duration of around {video_duration_secs} seconds.

    Each scene should consist of 1-2 sentences, get straight to the point, and must be related to the subject.

    YOU MUST NOT INCLUDE ANY TYPE OF MARKDOWN OR FORMATTING IN THE SCRIPT, NEVER USE A TITLE.

    YOU MUST WRITE THE SCRIPT IN English.

    ONLY RETURN THE RAW CONTENT OF THE SCRIPT. DO NOT INCLUDE "VOICEOVER", "NARRATOR" OR SIMILAR INDICATORS.

    YOU MUST NOT MENTION THE PROMPT, OR ANYTHING ABOUT THE SCRIPT ITSELF.

    JUST WRITE THE SCRIPT AS A JSON ARRAY OF STRINGS.

    Fact: "{video_topic}"
    """

    # Call the chat function with structured output
    response = call_openai_chat(
        prompt=prompt,
        functions=function_definition,
        function_call={"name": "generate_scene_list"}
    )

    print("\nGenerated Script:")
    print(response.get("scenes", []))
    print("\n")

    return response.get("scenes", [])


def generate_search_terms(video_topic: str, scripts: List[str]) -> List[str]:
    """
    Generates a list of search terms where each search term corresponds to a scene script.
    
    Args:
        video_topic (str): The main topic of the video.
        scripts (list): A list of scene scripts.
    
    Returns:
        list: A list of search terms corresponding to each scene.
    """
    # Define the function schema for structured output
    function_definition = [
        {
            "name": "generate_search_terms",
            "description": "Generates a list of search terms corresponding to each scene script for a YouTube video.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_terms": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "description": "A concise search term suitable for stock footage APIs like Pixabay or Pexels."
                        },
                        "description": "A list of search terms corresponding to each scene script."
                    }
                },
                "required": ["search_terms"]
            }
        }
    ]

    # Construct the prompt
    prompt = f'''
    You are an assistant that generates generic and commonly available search terms for each scene script of a YouTube video.
    Each search term should correspond to its respective scene script and be suitable for use with the Pixabay and Pexels APIs to find related video clips.

    **Important Instructions:**
    - The search terms must be generic and commonly available in stock footage, such as "people walking", "sunset", "city skyline", "nature landscape", "abstract patterns", "close-up of hands", etc.
    - Avoid specific names, events, or concepts that are unlikely to be found in stock footage.
    - Think about the main themes, emotions, and visuals that represent the content of each scene.
    - Use simple and broad terms that are likely to yield results on Pixabay or Pexels.
    - Every search term should be related to the video topic of the video (presented below) and not just a random word. So the "weight" of importance should always be the Topic itself, not just the content of an isolated scene.

    Below are the main topic and the scene scripts:

    Topic: "{video_topic}"

    Scene Scripts:
    '''
    for idx, script in enumerate(scripts):
        prompt += f"Scene {idx+1}: {script}\n"

    prompt += '''
    Generate a JSON object containing a "search_terms" array where each search term corresponds to its respective scene script.
    Ensure the order of search terms matches the order of the scene scripts.

    **Requirements:**
    - The JSON object should contain a "search_terms" array with the same number of search terms as there are scene scripts.
    - Each search term should be concise (1-3 words) and represent a generic concept, action, or object that aligns with the content of the corresponding scene.
    - Do not include any additional text, explanations, or markdown formatting. Only return the JSON object.

    Now, generate the search terms.
    '''

    # Call the chat function with structured output
    response = call_openai_chat(
        prompt=prompt,
        functions=function_definition,
        function_call={"name": "generate_search_terms"}
    )

    print("\nGenerated Search Terms:")
    print(response.get("search_terms", []))
    print("\n")

    return response.get("search_terms", [])


def generate_detailed_prompts(scenes: list):
    """
    Takes a list of short scene descriptions and returns a list of more detailed prompts,
    suitable for Luma AI generation.
    """
    # Define the function schema for structured output
    function_definition = [
        {
            "name": "generate_detailed_prompts_for_luma",
            "description": "Generates more detailed prompts for each scene to be used in Luma AI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "detailed_prompts": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "description": "A detailed prompt describing visual details."
                        }
                    }
                },
                "required": ["detailed_prompts"]
            }
        }
    ]

    # Construct the prompt for OpenAI
    scenes_text = "\n".join([f"- {scene}" for scene in scenes])
    prompt = f"""
    You are an assistant that transforms short scene descriptions into richly detailed visual prompts suitable for LumaAI.
    For each scene, craft a more elaborate description focusing on visual details, mood, environment, and style.

    Scenes:
    {scenes_text}

    Return the final result as a JSON array of strings ("detailed_prompts"), where each string corresponds to a detailed description for the respective scene.
    Do not include code blocks or any formatting other than the raw JSON array.
    """

    response = call_openai_chat(
        prompt=prompt,
        functions=function_definition,
        function_call={"name": "generate_detailed_prompts_for_luma"}
    )

    print("\nGenerated Detailed Prompts for Luma AI:")
    print(response.get("detailed_prompts", []))
    print("\n")

    return response.get("detailed_prompts", [])

    
def generate_video_title_and_hashtags(video_topic: str) -> Dict[str, List[str]]:
    """
    Generates a catchy video title and 5 relevant hashtags for YouTube based on the given topic.

    Args:
        video_topic (str): The topic of the video.

    Returns:
        dict: A dictionary containing "title" (str) and "hashtags" (list of strings).
    """
    # Define the function schema for structured output
    function_definition = [
        {
            "name": "generate_title_and_hashtags",
            "description": "Generates a catchy video title and 5 relevant hashtags for YouTube.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "A catchy title for the YouTube video.",
                    },
                    "hashtags": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "description": "A relevant hashtag for the video.",
                        },
                    },
                },
                "required": ["title", "hashtags"],
            },
        }
    ]

    # Construct the prompt
    prompt = f"""
    Based on the following fact, generate a catchy video title and 5 relevant hashtags for YouTube.

    Fact: "{video_topic}"
    """

    # Call the chat function with structured output
    response = call_openai_chat(
        prompt=prompt,
        functions=function_definition,
        function_call={"name": "generate_title_and_hashtags"}
    )

    print("Generated Video Title and Hashtags:")
    print(f"Title: {response['title']}")
    print(f"Hashtags: {', '.join(response['hashtags'])}")

    return response


if __name__ == "__main__":
    channel_subject = "Fun and lesser known facts"

    video_fact = generate_video_topic(channel_subject)
    if video_fact:
        scripts = generate_script(video_fact, '15')
        if scripts:
            detailed_prompts = generate_detailed_prompts(scripts)
        
            # Step 3: Generate video title and hashtags for YouTube
            title_and_hashtags = generate_video_title_and_hashtags(video_fact)
        else:
            print("No script and search terms generated.")
    else:
        print("No video fact generated.")
