import { OpenAIApi, Configuration } from 'openai';
import { config } from '@/config';

const openai = new OpenAIApi(new Configuration({ apiKey: config.openAIApiKey }));

export async function enhancePrompt(prompt: string): Promise<string> {
  try {
    const response = await openai.createCompletion({
      model: "text-davinci-002",
      prompt: `Enhance the following coding question for clarity and specificity:\n\n${prompt}\n\nEnhanced question:`,
      max_tokens: 100,
      temperature: 0.7,
    });

    const enhancedPrompt = response.data.choices[0].text?.trim() || prompt;
    return enhancedPrompt;
  } catch (error) {
    console.error('Error enhancing prompt:', error);
    return prompt; // Return original prompt if enhancement fails
  }
}

