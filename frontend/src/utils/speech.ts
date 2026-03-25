/**
 * Speaker — Utility for Text-to-Speech using browser native API.
 * High-fidelity, zero-latency, and privacy-first.
 */

export class Speaker {
  private synth: SpeechSynthesis;

  constructor() {
    this.synth = window.speechSynthesis;
  }

  speak(text: string, onEnd?: () => void): void {
    this.stop();

    // Clean text: remove markdown artifacts for better speech
    const cleanText = text
      .replace(/[*#_`]/g, '')
      .replace(/\[.*?\]\(.*?\)/g, '')
      .trim();

    const utterance = new SpeechSynthesisUtterance(cleanText);
    
    // Choose a premium sounding voice if available
    const voices = this.synth.getVoices();
    const premiumVoice = voices.find(v => v.name.includes('Google') && v.lang.startsWith('en')) || 
                        voices.find(v => v.lang.startsWith('en'));
    
    if (premiumVoice) utterance.voice = premiumVoice;
    
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;

    utterance.onend = () => {
      if (onEnd) onEnd();
    };

    this.synth.speak(utterance);
  }

  stop(): void {
    if (this.synth.speaking) {
      this.synth.cancel();
    }
  }

  get isSpeaking(): boolean {
    return this.synth.speaking;
  }
}

export const speaker = new Speaker();
