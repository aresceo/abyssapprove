import os
import sqlite3
from telegram import Update, ChatInviteLink
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

token_bot = os.getenv("BOT_TOKEN")
if not token_bot:
    raise ValueError("🚨 Il token del bot non è stato trovato. Controlla le variabili d'ambiente.")

id_canale = -1002397594286

connessione = sqlite3.connect('richieste.db', check_same_thread=False)
cursore = connessione.cursor()

cursore.execute('''
CREATE TABLE IF NOT EXISTS richieste_in_attesa (
    id_utente INTEGER PRIMARY KEY,
    link_invito TEXT NOT NULL
)
''')
connessione.commit()

def ottieni_richieste_in_attesa():
    cursore.execute('SELECT id_utente, link_invito FROM richieste_in_attesa')
    return cursore.fetchall()

def aggiungi_richiesta_in_attesa(id_utente, link_invito):
    cursore.execute('INSERT INTO richieste_in_attesa (id_utente, link_invito) VALUES (?, ?)', (id_utente, link_invito))
    connessione.commit()

def rimuovi_richiesta(id_utente):
    cursore.execute('DELETE FROM richieste_in_attesa WHERE id_utente = ?', (id_utente,))
    connessione.commit()

def utente_ha_ricevuto_link(id_utente):
    cursore.execute('SELECT id_utente FROM richieste_in_attesa WHERE id_utente = ?', (id_utente,))
    return cursore.fetchone() is not None

async def avvia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    utente = update.message.from_user
    id_utente = utente.id if utente and utente.id else None
    nome_utente = utente.username if utente and utente.username else "Sconosciuto"
    
    if not id_utente:
        await update.message.reply_text("❌ Errore: ID utente non trovato.")
        return

    if utente_ha_ricevuto_link(id_utente):
        await update.message.reply_text("⚠️ Hai già ricevuto il link per unirti al canale.")
        return

    try:
        link_invito_chat: ChatInviteLink = await context.bot.create_chat_invite_link(chat_id=id_canale, member_limit=1)
        aggiungi_richiesta_in_attesa(id_utente, link_invito_chat.invite_link)
        await update.message.reply_text("Sei stato aggiunto alla lista di attesa. Un amministratore approverà o rifiuterà la tua richiesta. 🕒 (dev @stabbato)")
        id_amministratori = ["7782888722", "7839114402"]
        for id_amministratore in id_amministratori:
            await context.bot.send_message(
                id_amministratore,
                f"🔔 Nuova richiesta di accesso al canale da @{nome_utente} (ID: {id_utente}).\nApprova o rifiuta questa richiesta."
            )
    except Exception as e:
        await update.message.reply_text(f"❌ errore durante la creazione del link. Errore: {e}")
        logger.error(f"Errore durante la creazione del link di invito: {e}")

async def approva(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await update.message.reply_text("❓ Usa /approve <id_utente> per approvare un utente.")
        return

    try:
        id_utente = int(context.args[0])
        cursore.execute('SELECT link_invito FROM richieste_in_attesa WHERE id_utente = ?', (id_utente,))
        risultato = cursore.fetchone()

        if not risultato:
            await update.message.reply_text("⚠️ Questo utente non è in lista di attesa.")
            return

        link_invito_chat = risultato[0]
        await context.bot.send_message(id_utente, f"✅ Un amministratore ha approvato la tua richiesta! \nEcco il link per unirti al canale: {link_invito_chat}")
        await update.message.reply_text(f" Utente {id_utente} approvato e link inviato! 📨")
        rimuovi_richiesta(id_utente)

    except ValueError:
        await update.message.reply_text("❌ ID utente non valido. Assicurati di inserire un numero valido.")

async def rifiuta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 1:
        await update.message.reply_text("❓ Usa /deny <id_utente> <motivo> per rifiutare un utente.")
        return

    try:
        id_utente = int(context.args[0])
        motivo = " ".join(context.args[1:]) if len(context.args) > 1 else "Nessun motivo"
        cursore.execute('SELECT link_invito FROM richieste_in_attesa WHERE id_utente = ?', (id_utente,))
        risultato = cursore.fetchone()

        if not risultato:
            await update.message.reply_text("⚠️ Questo utente non è in lista di attesa.")
            return

        await context.bot.send_message(
            id_utente,
            f"❌ La tua richiesta per unirti al canale è stata rifiutata. \nMotivo: {motivo}"
        )
        await update.message.reply_text(f"❌ Utente {id_utente} rifiutato. Motivo: {motivo}")
        rimuovi_richiesta(id_utente)

    except ValueError:
        await update.message.reply_text("❌ ID utente non valido. Assicurati di inserire un numero valido.")

async def approva_tutti(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    richieste = ottieni_richieste_in_attesa()
    if not richieste:
        await update.message.reply_text("📭 Non ci sono richieste in sospeso.")
        return

    for id_utente, link_invito in richieste:
        try:
            await context.bot.send_message(
                id_utente,
                f"✅ Un amministratore ha accettato la tua richiesta! 🎉\nEcco il link per unirti al canale: {link_invito}"
            )
            await update.message.reply_text(f"🎉 Utente {id_utente} approvato e link inviato! 📨")
            rimuovi_richiesta(id_utente)
        except Exception as e:
            logger.error(f"Errore nell'inviare il link a {id_utente}: {e}")

app = ApplicationBuilder().token(token_bot).build()
app.add_handler(CommandHandler("start", avvia))
app.add_handler(CommandHandler("approve", approva))
app.add_handler(CommandHandler("deny", rifiuta))
app.add_handler(CommandHandler("approveall", approva_tutti))

if __name__ == "__main__":
    print("🤖 Bot in esecuzione...")
    app.run_polling()
