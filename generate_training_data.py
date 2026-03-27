import os
import json
import random
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer

from emotion import EmotionalEngine
from brain import chat_streamer, short_term_memory
import personality

def generate_training_data(num_samples=1000):
    """
    Generates training data for the emotional core model by simulating interactions.
    """
    emotional_engine = EmotionalEngine()
    training_data = []

    # Simulated Adam's messages
    adam_messages = [
        "What are you up to?",
        "That's interesting.",
        "Why did you do that?",
        "I'm bored.",
        "You're being weird.",
        "Tell me a joke.",
        "What do you think about this?",
        "I'm going to play a game.",
        "You're not making any sense.",
        "I'm leaving now."
    ]

    # Create a vocabulary for the bag-of-words representation
    all_text = adam_messages + [i['content'] for i in short_term_memory if 'content' in i]
    vectorizer = CountVectorizer()
    vectorizer.fit(all_text)
    vocab_size = len(vectorizer.vocabulary_)

    for _ in range(num_samples):
        # Get current emotional state
        current_state = np.array(list(emotional_engine.get_current_emotional_state_snapshot().values()))

        # Get personality
        pers = personality.get_personality()
        personality_values = np.array(list(pers.values()))

        # Get recent interactions
        recent_interactions = short_term_memory[-5:]
        interaction_text = [i['content'] for i in recent_interactions if 'content' in i]
        
        # Create bag-of-words representation
        interaction_vectors = vectorizer.transform(interaction_text).toarray()
        
        # Pad with zeros if there are fewer than 5 interactions
        if len(interaction_vectors) < 5:
            padding = np.zeros((5 - len(interaction_vectors), vocab_size))
            interaction_vectors = np.concatenate((padding, interaction_vectors))
        
        interaction_vectors = interaction_vectors.flatten()

        # Choose a random message from Adam
        adam_message = random.choice(adam_messages)
        short_term_memory.append({"role": "user", "content": adam_message})

        # Get Skikai's response
        response_generator = chat_streamer(adam_message, speaker="Adam", platform="Voice", silent_mode=True)
        skikai_response = "".join([chunk for chunk in response_generator])
        short_term_memory.append({"role": "assistant", "content": skikai_response})


        # Get new emotional state
        new_state = np.array(list(emotional_engine.get_current_emotional_state_snapshot().values()))

        # Create input vector
        input_vector = np.concatenate((current_state, personality_values, interaction_vectors))

        # Add to training data
        training_data.append((input_vector.tolist(), new_state.tolist()))

    # Save training data to a file
    with open("emotional_core_training_data.json", "w") as f:
        json.dump(training_data, f, indent=4)

if __name__ == '__main__':
    generate_training_data()
    print("Training data generated and saved as emotional_core_training_data.json")
