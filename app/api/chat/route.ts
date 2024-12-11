import { NextResponse } from 'next/server'
import { v0 } from '@vercel/v0'
import { Claude } from '@anthropic-ai/sdk'
import { Configuration, OpenAIApi } from 'openai'
import { BoltAI } from '@bolt-ai/sdk'
import { enhancePrompt } from '@/utils/promptEnhancer'
import { aggregateResponses } from '@/utils/responseAggregator'
import { getCachedResponse, setCachedResponse } from '@/utils/cache'
import { config } from '@/config'
import prisma from '@/lib/prisma'

const v0Client = v0.createClient({ apiKey: config.v0ApiKey })
const claude = new Claude(config.claudeApiKey)
const openai = new OpenAIApi(new Configuration({ apiKey: config.openAIApiKey }))
const boltAI = new BoltAI(config.boltAIApiKey)

export async function POST(req: Request) {
  const { message, model, userId } = await req.json()

  try {
    const cacheKey = `${userId}:${message}`
    const cachedResponse = await getCachedResponse(cacheKey)

    if (cachedResponse) {
      return NextResponse.json({ response: cachedResponse })
    }

    const enhancedPrompt = await enhancePrompt(message)

    if (model) {
      let response
      switch (model) {
        case 'v0':
          response = await v0Client.generateCode({ prompt: enhancedPrompt })
          break
        case 'claude':
          response = await claude.complete({ prompt: enhancedPrompt })
          break
        case 'chatgpt':
          const completion = await openai.createCompletion({ model: "text-davinci-002", prompt: enhancedPrompt })
          response = completion.data.choices[0].text
          break
        case 'bolt':
          response = await boltAI.generate({ prompt: enhancedPrompt })
          break
        default:
          throw new Error('Invalid model specified')
      }
      await setCachedResponse(cacheKey, response)
      await prisma.message.create({
        data: {
          content: response,
          role: 'assistant',
          model: model,
          userId: userId,
        },
      })
      return NextResponse.json({ response })
    } else {
      const [v0Response, claudeResponse, chatGPTResponse, boltResponse] = await Promise.all([
        v0Client.generateCode({ prompt: enhancedPrompt }),
        claude.complete({ prompt: enhancedPrompt }),
        openai.createCompletion({ model: "text-davinci-002", prompt: enhancedPrompt }),
        boltAI.generate({ prompt: enhancedPrompt })
      ])

      const aggregatedResponse = await aggregateResponses([
        v0Response,
        claudeResponse,
        chatGPTResponse.data.choices[0].text,
        boltResponse
      ])

      await setCachedResponse(cacheKey, aggregatedResponse)
      await prisma.message.create({
        data: {
          content: aggregatedResponse,
          role: 'assistant',
          userId: userId,
        },
      })
      return NextResponse.json({ response: aggregatedResponse })
    }
  } catch (error) {
    console.error('Error:', error)
    return NextResponse.json({ error: 'An error occurred while processing your request.' }, { status: 500 })
  }
}

