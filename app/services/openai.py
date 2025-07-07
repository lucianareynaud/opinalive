import openai
from ..config import settings
import json
import logging
import hashlib

logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
    
    def generate_client_hash(self, client_identifier: str, business_id: int) -> str:
        """
        Gera um hash anônimo para o cliente que é consistente para o mesmo business
        """
        # Combina o identificador do cliente com o ID do business para garantir unicidade
        unique_string = f"{client_identifier}:{business_id}"
        return hashlib.sha256(unique_string.encode()).hexdigest()[:12]
    
    async def analyze_feedback(self, text: str) -> dict:
        """
        Análise detalhada do feedback usando GPT-4
        """
        prompt = f"""
        Analise este feedback de cliente em português e forneça uma análise detalhada no seguinte formato JSON:
        {{
            "sentiment": "POSITIVO/NEGATIVO/NEUTRO",
            "sentiment_score": float entre -1.0 e 1.0,
            "inferred_rating": int entre 1 e 5 estrelas,
            "emotions": ["emoção1", "emoção2"],
            "key_phrases": ["frase impactante 1", "frase impactante 2"],
            "is_compliment": true/false,
            "is_complaint": true/false,
            "action_items": ["sugestão de ação 1", "sugestão de ação 2"],
            "topics": ["tópico 1", "tópico 2"],
            "intent": {{"primary": "principal intenção", "secondary": ["intenção secundária 1", "intenção secundária 2"]}},
            "urgency": "ALTA/MÉDIA/BAIXA",
            "customer_satisfaction": {{"level": "SATISFEITO/INSATISFEITO/NEUTRO", "reasons": ["razão 1", "razão 2"]}},
            "product_mentions": ["produto/serviço mencionado 1", "produto/serviço mencionado 2"],
            "improvement_areas": ["área de melhoria 1", "área de melhoria 2"]
        }}

        Regras:
        1. sentiment_score: -1.0 (muito negativo) até 1.0 (muito positivo)
        2. inferred_rating: 1 (péssimo) até 5 (excelente)
        3. emotions: identifique emoções expressas (ex: frustração, alegria, gratidão)
        4. key_phrases: extraia 2-3 frases mais impactantes e relevantes
        5. action_items: sugira 1-3 ações concretas baseadas no feedback
        6. topics: identifique 1-3 tópicos principais mencionados
        7. intent: identifique a principal intenção e intenções secundárias
        8. urgency: classifique com base na necessidade de ação imediata
        9. improvement_areas: sugira áreas específicas para melhoria

        Feedback: {text}
        """
        
        try:
            response = await openai.ChatCompletion.acreate(
                model=settings.OPENAI_ANALYSIS_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Você é um especialista em análise de feedback de clientes, focado em extrair insights acionáveis para melhorar negócios."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=800
            )
            
            # Parse the JSON response
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            logger.error(f"Error in feedback analysis: {e}")
            return {
                "sentiment": "unknown",
                "sentiment_score": 0.0,
                "inferred_rating": None,
                "emotions": [],
                "key_phrases": [],
                "is_compliment": False,
                "is_complaint": False,
                "action_items": [],
                "topics": [],
                "intent": {"primary": None, "secondary": []},
                "urgency": "BAIXA",
                "customer_satisfaction": {"level": "NEUTRO", "reasons": []},
                "product_mentions": [],
                "improvement_areas": []
            } 