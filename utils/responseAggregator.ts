import { OpenAIApi, Configuration } from 'openai';
import { config } from '@/config';

const openai = new OpenAIApi(new Configuration({ apiKey: config.openAIApiKey }));

export async function aggregateResponses(responses: string[]): Promise<string> {
  const combinedResponses = responses.join('\n\n');

  try {
    const response = await openai.createCompletion({
      model: "text-davinci-002",
      prompt: `Analyze and combine the following AI responses to a coding question, providing the most accurate and comprehensive answer:\n\n${combinedResponses}\n\nCombined response:`,
      max_tokens: 500,
      temperature: 0.5,
    });

    const aggregatedResponse = response.data.choices[0].text?.trim() || combinedResponses;
    return aggregatedResponse;
  } catch (error) {
    console.error('Error aggregating responses:', error);
    return combinedResponses; // Return combined responses if aggregation fails
  }
}

