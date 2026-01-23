
import random
from typing import List, Tuple

class Card:
    def __init__(self, suit: str, rank: str):
        self.suit = suit
        self.rank = rank
        
    def __str__(self):
        return f"{self.rank}{self.suit}"
        
    @property
    def value(self) -> int:
        if self.rank in ["J", "Q", "K"]:
            return 10
        elif self.rank == "A":
            return 11
        return int(self.rank)

class Deck:
    def __init__(self):
        self.suits = ["♠", "♥", "♣", "♦"]
        self.ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        self.cards = [Card(s, r) for s in self.suits for r in self.ranks]
        random.shuffle(self.cards)
        
    def draw(self) -> Card:
        if not self.cards:
            self.__init__() # Reshuffle if empty
        return self.cards.pop()

def calculate_hand_value(cards: List[Card]) -> int:
    """Calculate the value of a hand, handling Aces correctly."""
    total = 0
    aces = 0
    
    for card in cards:
        total += card.value
        if card.rank == "A":
            aces += 1
            
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
        
    return total

def format_hand(cards: List[Card], hidden: bool = False) -> str:
    """Format hand for display. If hidden is True, hide the second card."""
    if hidden and len(cards) >= 1:
        return f"[{str(cards[0])}, ??]"
    return f"[{', '.join(str(c) for c in cards)}]"
