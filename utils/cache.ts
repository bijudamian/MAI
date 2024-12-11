import { createClient } from 'redis';
import { config } from '@/config';

const redisClient = createClient({ url: config.redisUrl });

redisClient.on('error', (err) => console.log('Redis Client Error', err));

export async function getCachedResponse(key: string): Promise<string | null> {
  await redisClient.connect();
  const cachedResponse = await redisClient.get(key);
  await redisClient.disconnect();
  return cachedResponse;
}

export async function setCachedResponse(key: string, value: string, expirationInSeconds: number = 3600): Promise<void> {
  await redisClient.connect();
  await redisClient.set(key, value, { EX: expirationInSeconds });
  await redisClient.disconnect();
}

