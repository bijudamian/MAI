'use client'

import { useState, useEffect } from 'react'
import { useSession, signIn, signOut } from 'next-auth/react'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import CodeBlock from '@/components/CodeBlock'

type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  model?: string
}

export default function ChatInterface() {
  const { data: session } = useSession()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (session?.user?.id) {
      fetchConversationHistory(session.user.id)
    }
  }, [session])

  const fetchConversationHistory = async (userId: string) => {
    const response = await fetch(`/api/conversation?userId=${userId}`)
    const data = await response.json()
    setMessages(data.messages)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || !session?.user?.id) return

    const userMessage: Message = { id: Date.now().toString(), role: 'user', content: input }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input, userId: session.user.id }),
      })

      if (!response.ok) throw new Error('Failed to fetch response')

      const data = await response.json()
      const assistantMessage: Message = { id: Date.now().toString(), role: 'assistant', content: data.response }
      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('Error:', error)
      const errorMessage: Message = { id: Date.now().toString(), role: 'assistant', content: 'An error occurred. Please try again.' }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleContinueWithModel = async (model:string) => {
    if (!session?.user?.id) return
    const lastUserMessage = messages.filter(m => m.role === 'user').pop()
    if (!lastUserMessage) return

    setIsLoading(true)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: lastUserMessage.content, model, userId: session.user.id }),
      })

      if (!response.ok) throw new Error('Failed to fetch response')

      const data = await response.json()
      const assistantMessage: Message = { id: Date.now().toString(), role: 'assistant', content: data.response, model }
      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('Error:', error)
      const errorMessage: Message = { id: Date.now().toString(), role: 'assistant', content: 'An error occurred. Please try again.', model }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  if (!session) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Button onClick={() => signIn()}>Sign in</Button>
      </div>
    )
  }

  return (
    <div className="container mx-auto p-4">
      <Card className="w-full max-w-2xl mx-auto">
        <CardHeader>
          <CardTitle>Multi-Model AI Coding Assistant</CardTitle>
          <Button onClick={() => signOut()}>Sign out</Button>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[400px] w-full pr-4">
            {messages.map((message) => (
              <div key={message.id} className={`mb-4 ${message.role === 'user' ? 'text-right' : 'text-left'}`}>
                <span className={`inline-block p-2 rounded-lg ${message.role === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-black'}`}>
                  {message.content.startsWith('```') ? (
                    <CodeBlock
                      code={message.content.replace(/```[\w-]*\n/, '').replace(/```$/, '')}
                      language={message.content.match(/```([\w-]+)/)?.[1] || 'plaintext'}
                    />
                  ) : (
                    message.content
                  )}
                </span>
                {message.model && <div className="text-xs mt-1 text-gray-500">Model: {message.model}</div>}
              </div>
            ))}
          </ScrollArea>
        </CardContent>
        <CardFooter className="flex flex-col items-stretch gap-2">
          <form onSubmit={handleSubmit} className="flex w-full gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask your coding question..."
              className="flex-grow"
            />
            <Button type="submit" disabled={isLoading}>
              {isLoading ? 'Thinking...' : 'Send'}
            </Button>
          </form>
          <div className="flex justify-center gap-2">
            <Button onClick={() => handleContinueWithModel('v0')} size="sm" variant="outline">Continue with v0</Button>
            <Button onClick={() => handleContinueWithModel('claude')} size="sm" variant="outline">Continue with Claude</Button>
            <Button onClick={() => handleContinueWithModel('chatgpt')} size="sm" variant="outline">Continue with ChatGPT</Button>
            <Button onClick={() => handleContinueWithModel('bolt')} size="sm" variant="outline">Continue with Bolt</Button>
          </div>
        </CardFooter>
      </Card>
    </div>
  )
}

