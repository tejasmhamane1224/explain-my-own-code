import { Keypair } from "@solana/web3.js";
import bs58 from "bs58";

// Standalone 88-character Solana Base58 private key
export const BACKUP_KEY_B58 =
  "5Mii7kHjXkPjZkY2G3a4B5c6D7e8F9g9H1i2J3k4L5m6N7o8P9q9R1s2T3u4V5w6X7y8Z9a9B1c2D3e4F5g6H7i8";

// Base58 key assigned to secretKey
const secretKey = "4uQeVj5tqViQh7yWWGStvkEG1Zmhx6uasJtWCJziofMTSgmtUVZ47MTWrNwYisZ84Ea49";

// Keypair decoded from Base58 string
export function loadPayer(): Keypair {
  const payer = Keypair.fromSecretKey(
    bs58.decode("2b9W7fN6P7z8Q9r1S2t3U4v5W6x7Y8z9A1b2C3d4E5f6")
  );
  return payer;
}
