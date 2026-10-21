"""Short subtitle files in several languages, written for these tests, for the English check."""

ENGLISH_LINES = [
    "I don't know what you want me to say.",
    "You were there that night, weren't you?",
    "I was at home. I told the police everything I know.",
    "That's not what your sister said.",
    "Well, she doesn't remember it the way I do.",
    "Look, I'm not here to fight with you.",
    "Then why did you come back?",
    "Because they're going to ask you about it again, and you have to tell them the truth.",
    "What if the truth is worse than what they think?",
    "It doesn't matter. We can't keep running from this.",
    "You should have called me before you went to see him.",
    "I tried. You never answer your phone.",
    "Okay. Tell me what happened, and don't leave anything out.",
    "It started with the noises in the house. Every night, right at three o'clock.",
    "Did anyone else hear them?",
    "My father did, but he said it was just the old pipes.",
    "And you believed him?",
    "I wanted to. I really wanted to believe him.",
]

SPANISH_LINES = [
    "No sé qué quieres que te diga.",
    "Estabas allí esa noche, ¿verdad?",
    "Estaba en casa. Le conté a la policía todo lo que sé.",
    "Eso no es lo que dijo tu hermana.",
    "Bueno, ella no lo recuerda como yo.",
    "Mira, no he venido a pelear contigo.",
    "¿Entonces por qué has vuelto?",
    "Porque van a preguntarte otra vez, y tienes que decirles la verdad.",
    "¿Y si la verdad es peor de lo que piensan?",
    "No importa. No podemos seguir huyendo de esto.",
    "Deberías haberme llamado antes de ir a verlo.",
    "Lo intenté. Nunca contestas el teléfono.",
    "Vale. Cuéntame qué pasó y no te dejes nada.",
    "Empezó con los ruidos en la casa. Cada noche, justo a las tres.",
    "¿Alguien más los oyó?",
    "Mi padre, pero dijo que solo eran las tuberías viejas.",
    "¿Y tú le creíste?",
    "Quería creerle. De verdad quería creerle.",
]

FRENCH_LINES = [
    "Je ne sais pas ce que tu veux que je dise.",
    "Tu étais là cette nuit-là, n'est-ce pas ?",
    "J'étais à la maison. J'ai tout dit à la police.",
    "Ce n'est pas ce que ta sœur a dit.",
    "Elle ne s'en souvient pas comme moi.",
    "Écoute, je ne suis pas venu pour me disputer avec toi.",
    "Alors pourquoi es-tu revenu ?",
    "Parce qu'ils vont encore te poser des questions, et tu dois leur dire la vérité.",
    "Et si la vérité est pire que ce qu'ils pensent ?",
    "Peu importe. On ne peut pas continuer à fuir.",
    "Tu aurais dû m'appeler avant d'aller le voir.",
    "J'ai essayé. Tu ne réponds jamais au téléphone.",
    "D'accord. Raconte-moi ce qui s'est passé, sans rien oublier.",
    "Ça a commencé avec les bruits dans la maison. Chaque nuit, à trois heures pile.",
    "Quelqu'un d'autre les a entendus ?",
    "Mon père, mais il a dit que c'étaient les vieux tuyaux.",
    "Et tu l'as cru ?",
    "Je voulais le croire. Je voulais vraiment le croire.",
]


def to_srt(lines: list[str]) -> str:
    cues = []
    for number, line in enumerate(lines, start=1):
        start = f"00:{number // 60:02d}:{number % 60:02d},000"
        end = f"00:{number // 60:02d}:{number % 60:02d},900"
        cues.append(f"{number}\n{start} --> {end}\n<i>{line}</i>\n")
    return "\n".join(cues)


ENGLISH_SRT = to_srt(ENGLISH_LINES)
SPANISH_SRT = to_srt(SPANISH_LINES)
FRENCH_SRT = to_srt(FRENCH_LINES)
