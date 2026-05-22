"""
Localized WhatsApp reply templates for system-generated messages
(i.e. messages NOT written by the AI — used when we override the AI response
for specific flow states like awaiting_location).

Each template receives keyword arguments matching the format() placeholders.
Language keys match the detected_language values returned by ai_engine.py.
"""


def _mostly_ascii(text: str) -> bool:
    stripped = [c for c in (text or "") if not c.isspace()]
    if not stripped:
        return True
    ascii_count = sum(1 for c in stripped if ord(c) < 128)
    return (ascii_count / len(stripped)) >= 0.90


def normalize_language_name(detected_language: str = "", default: str = "") -> str:
    """Return a canonical supported language name without inventing Hindi."""
    return _LANG_ALIASES.get((detected_language or "").lower().strip(), default)


def _normalize_language(detected_language: str = "") -> str:
    return normalize_language_name(detected_language, "Hindi")


def _pick_template(native_templates: dict[str, str], latin_templates: dict[str, str], detected_language: str = "", original_text: str = "") -> str:
    normalized = _normalize_language(detected_language)
    if original_text and _mostly_ascii(original_text) and normalized in latin_templates:
        return latin_templates[normalized]
    return native_templates.get(normalized, native_templates.get("Hindi", ""))


def ensure_ji_prefix(reply: str) -> str:
    text = str(reply or "").strip()
    if not text:
        return "Ji,"
    if text.lower().startswith("ji,") or text.lower().startswith("ji "):
        return text
    return f"Ji, {text}"

# ── Awaiting Location ────────────────────────────────────────────────────────
# Sent when the AI sets status='awaiting_location' because the mentioned
# location couldn't be matched to a known constituency.
# Placeholder: {location}

_AWAITING_LOCATION: dict[str, str] = {
    "Hindi": (
        "Aapka sandesh mila, shukriya 🙏\n\n"
        "Aapne *{location}* ka zikr kiya — lekin hum ise poori tarah pehchan nahi paaye. "
        "Kya aap thoda aur bata sakte hain?\n\n"
        "Jaise ki:\n"
        "• Gaon ya mohalle ka naam\n"
        "• Nagar panchayat / ward number\n"
        "• Koi paas ka landmark\n\n"
        "Jaise hi location clear hogi, hum turant aapki baat aage badhayenge. 🙏"
    ),
    "Hinglish": (
        "Aapka message mil gaya, thank you 🙏\n\n"
        "Aapne *{location}* mention kiya — but hum exact location identify nahi kar paaye. "
        "Kya aap thoda aur detail de sakte hain?\n\n"
        "For example:\n"
        "• Village / Mohalla name\n"
        "• Ward number\n"
        "• Nearest landmark\n\n"
        "Location confirm hote hi hum aapka issue sahi team tak pahucha denge. 🙏"
    ),
    "Marathi": (
        "तुमचा संदेश मिळाला, धन्यवाद 🙏\n\n"
        "तुम्ही *{location}* चा उल्लेख केला — पण आम्हाला नक्की ठिकाण ओळखता आलं नाही. "
        "थोडं अधिक सांगू शकता का?\n\n"
        "उदाहरणार्थ:\n"
        "• गाव किंवा मोहल्ल्याचे नाव\n"
        "• नगर पंचायत / वार्ड नंबर\n"
        "• जवळचा कोणता landmark\n\n"
        "location स्पष्ट झाल्यावर आम्ही लगेच पुढची कार्यवाही करू. 🙏"
    ),
    "Tamil": (
        "உங்கள் செய்தி கிடைத்தது, நன்றி 🙏\n\n"
        "நீங்கள் *{location}* பற்றி கூறினீர்கள் — ஆனால் சரியான இடத்தை கண்டறிய முடியவில்லை. "
        "கொஞ்சம் விரிவாக சொல்ல முடியுமா?\n\n"
        "எடுத்துக்காட்டாக:\n"
        "• கிராமம் அல்லது பகுதியின் பெயர்\n"
        "• வார்டு எண்\n"
        "• அருகிலுள்ள landmark\n\n"
        "இடம் தெளிவானதும் உடனே நடவடிக்கை எடுப்போம். 🙏"
    ),
    "Telugu": (
        "మీ సందేశం అందింది, ధన్యవాదాలు 🙏\n\n"
        "మీరు *{location}* గురించి చెప్పారు — కానీ సరిగ్గా ఆ ప్రదేశాన్ని గుర్తించలేకపోయాం. "
        "కొంచెం వివరంగా చెప్పగలరా?\n\n"
        "ఉదాహరణకు:\n"
        "• గ్రామం లేదా మొహల్లా పేరు\n"
        "• వార్డు నంబర్\n"
        "• దగ్గరలో ఉన్న landmark\n\n"
        "స్థలం నిర్ధారణ అయిన వెంటనే చర్యలు తీసుకుంటాం. 🙏"
    ),
    "Kannada": (
        "ನಿಮ್ಮ ಸಂದೇಶ ಬಂದಿದೆ, ಧನ್ಯವಾದಗಳು 🙏\n\n"
        "ನೀವು *{location}* ಬಗ್ಗೆ ತಿಳಿಸಿದ್ದೀರಿ — ಆದರೆ ನಿಖರವಾದ ಸ್ಥಳವನ್ನು ಗುರುತಿಸಲು ಆಗಲಿಲ್ಲ. "
        "ಸ್ವಲ್ಪ ಹೆಚ್ಚು ವಿವರ ಹೇಳಬಹುದೇ?\n\n"
        "ಉದಾಹರಣೆಗೆ:\n"
        "• ಗ್ರಾಮ ಅಥವಾ ಮೊಹಲ್ಲಾ ಹೆಸರು\n"
        "• ವಾರ್ಡ್ ಸಂಖ್ಯೆ\n"
        "• ಹತ್ತಿರದ landmark\n\n"
        "ಸ್ಥಳ ಖಚಿತವಾದ ತಕ್ಷಣ ಮುಂದಿನ ಕ್ರಮ ತೆಗೆದುಕೊಳ್ಳುತ್ತೇವೆ. 🙏"
    ),
    "Malayalam": (
        "നിങ്ങളുടെ സന്ദേശം ലഭിച്ചു, നന്ദി 🙏\n\n"
        "നിങ്ങൾ *{location}* പ്പറ്റി പറഞ്ഞു — എന്നാൽ ആ സ്ഥലം കൃത്യമായി തിരിച്ചറിയാൻ കഴിഞ്ഞില്ല. "
        "അൽപം കൂടി വിശദമായി പറയാമോ?\n\n"
        "ഉദാഹരണം:\n"
        "• ഗ്രാമം അല്ലെങ്കിൽ മൊഹല്ലയുടെ പേര്\n"
        "• വാർഡ് നമ്പർ\n"
        "• അടുത്തുള്ള landmark\n\n"
        "സ്ഥലം വ്യക്തമായാൽ ഉടൻ നടപടി എടുക്കാം. 🙏"
    ),
    "Bengali": (
        "আপনার বার্তা পেয়েছি, ধন্যবাদ 🙏\n\n"
        "আপনি *{location}*-এর কথা উল্লেখ করেছেন — কিন্তু সঠিক এলাকাটি চিহ্নিত করা যাচ্ছে না। "
        "একটু বিস্তারিত বলতে পারবেন কি?\n\n"
        "যেমন:\n"
        "• গ্রাম বা মহল্লার নাম\n"
        "• ওয়ার্ড নম্বর\n"
        "• কাছাকাছি কোনো landmark\n\n"
        "সঠিক জায়গা জানলেই আমরা দ্রুত ব্যবস্থা নেব। 🙏"
    ),
    "Gujarati": (
        "તમારો સંદેશ મળ્યો, આભાર 🙏\n\n"
        "તમે *{location}* નો ઉલ્લેખ કર્યો — પરંતુ ચોક્કસ સ્થળ ઓળખી શકાયું નહીં. "
        "શું થોડી વધુ માહિતી આપી શકો?\n\n"
        "જેમ કે:\n"
        "• ગામ અથવા મહોલ્લાનું નામ\n"
        "• વોર્ડ નંબર\n"
        "• નજીકનો landmark\n\n"
        "સ્થળ સ્પષ્ટ થાય કે તરત જ આગળની કાર્યવાહી કરીશું. 🙏"
    ),
    "Punjabi": (
        "ਤੁਹਾਡਾ ਸੁਨੇਹਾ ਮਿਲਿਆ, ਧੰਨਵਾਦ 🙏\n\n"
        "ਤੁਸੀਂ *{location}* ਦਾ ਜ਼ਿਕਰ ਕੀਤਾ — ਪਰ ਅਸੀਂ ਸਹੀ ਥਾਂ ਪਛਾਣ ਨਹੀਂ ਸਕੇ। "
        "ਕੀ ਤੁਸੀਂ ਥੋੜਾ ਹੋਰ ਦੱਸ ਸਕਦੇ ਹੋ?\n\n"
        "ਜਿਵੇਂ:\n"
        "• ਪਿੰਡ ਜਾਂ ਮੁਹੱਲੇ ਦਾ ਨਾਂ\n"
        "• ਵਾਰਡ ਨੰਬਰ\n"
        "• ਨੇੜੇ ਦਾ landmark\n\n"
        "ਥਾਂ ਪੱਕੀ ਹੁੰਦੀ ਸਾਰ ਅਸੀਂ ਅੱਗੇ ਕਾਰਵਾਈ ਕਰਾਂਗੇ। 🙏"
    ),
    "Odia": (
        "ଆପଣଙ୍କ ବାର୍ତ୍ତା ମିଳିଲା, ଧନ୍ୟବାଦ 🙏\n\n"
        "ଆପଣ *{location}* ବିଷୟରେ କହିଥିଲେ — କିନ୍ତୁ ସଠିକ ଜାଗା ଚିହ୍ନଟ ହୋଇ ପାରିଲା ନାହିଁ। "
        "ଆଉ ଟିକିଏ ବିସ୍ତୃତ ଭାବରେ କହିବେ କି?\n\n"
        "ଯଥା:\n"
        "• ଗ୍ରାମ ବା ମୁହଲ୍ଲାର ନାମ\n"
        "• ୱାର୍ଡ ନମ୍ବର\n"
        "• ନିକଟ landmark\n\n"
        "ସ୍ଥାନ ସ୍ପଷ୍ଟ ହେବା ମାତ୍ରେ ଆମେ ତୁରନ୍ତ ପଦକ୍ଷେପ ନେବୁ। 🙏"
    ),
    "Assamese": (
        "আপোনাৰ বার্তা পালোঁ, ধন্যবাদ 🙏\n\n"
        "আপুনি *{location}*-ৰ কথা উল্লেখ কৰিলে — কিন্তু সঠিক ঠাইটো চিনাক্ত কৰিব পৰা নগ'ল। "
        "অলপ বিস্তাৰিতকৈ ক'ব পাৰিবনে?\n\n"
        "যেনে:\n"
        "• গাঁও বা মহল্লাৰ নাম\n"
        "• ৱাৰ্ড নম্বৰ\n"
        "• ওচৰৰ কোনো landmark\n\n"
        "ঠাই নিশ্চিত হ'লেই আমি তৎক্ষণাৎ ব্যৱস্থা ল'ম। 🙏"
    ),
    "Urdu": (
        "آپ کا پیغام مل گیا، شکریہ 🙏\n\n"
        "آپ نے *{location}* کا ذکر کیا — لیکن ہم بالکل صحیح جگہ پہچان نہیں سکے۔ "
        "کیا آپ تھوڑا اور بتا سکتے ہیں؟\n\n"
        "مثلاً:\n"
        "• گاؤں یا محلے کا نام\n"
        "• وارڈ نمبر\n"
        "• قریب کا کوئی مشہور مقام\n\n"
        "جگہ واضح ہوتے ہی ہم فوری کارروائی کریں گے۔ 🙏"
    ),
    "English": (
        "Thank you for reaching out 🙏\n\n"
        "You mentioned *{location}* — but we weren't able to identify the exact area. "
        "Could you share a bit more detail?\n\n"
        "For example:\n"
        "• Village or neighbourhood name\n"
        "• Ward number\n"
        "• Nearest landmark\n\n"
        "Once we have the location, we'll make sure your issue reaches the right team right away."
    ),
}

# Default fallback — covers any language not explicitly listed
_DEFAULT_AWAITING_LOCATION = _AWAITING_LOCATION["Hindi"]

_AWAITING_LOCATION_LATIN: dict[str, str] = {
    "Hindi": (
        "Aapka sandesh mila, dhanyavaad 🙏\n\n"
        "Aapne *{location}* ka zikr kiya, lekin humein exact jagah samajh nahi aayi. "
        "Kripya thoda aur vivaran bhejiye.\n\n"
        "Jaise:\n"
        "• Gaon ya mohalla ka naam\n"
        "• Ward number\n"
        "• Koi paas ka landmark\n\n"
        "Location clear hote hi hum turant aage ki karvayi karenge. 🙏"
    ),
    "Hinglish": _AWAITING_LOCATION["Hinglish"],
    "Marathi": (
        "Tumcha sandesh milala, dhanyavaad 🙏\n\n"
        "Tumhi *{location}* cha ullekh kela, pan amhala exact thikan olakhata ala nahi. "
        "Krupaya thoda adhik mahiti pathva.\n\n"
        "Udaharanarth:\n"
        "• Gaav kiwa mohalla che naav\n"
        "• Ward number\n"
        "• Javalcha landmark\n\n"
        "Location spashta zalyavar amhi turant pudhil karvayi karu. 🙏"
    ),
}


_GENERIC_ACK: dict[str, str] = {
    "Hindi": (
        "Aapka sandesh mil gaya hai 🙏\n\n"
        "Aapki samasya darj kar li gayi hai aur iski samiksha ki ja rahi hai. "
        "Hum jald hi aapse sampark karenge."
    ),
    "Hinglish": (
        "Aapka message mil gaya hai 🙏\n\n"
        "Aapka issue register ho gaya hai aur review kiya ja raha hai. "
        "Hum aapse jald contact karenge."
    ),
    "Marathi": (
        "Tumcha sandesh milala aahe 🙏\n\n"
        "Tumchi samasya nondi keli aahe ani ti sadhya tapast aahe. "
        "Amhi lokerach tumchyashi sampark karu."
    ),
    "Kannada": (
        "Nimma sandesha siggide 🙏\n\n"
        "Nimma samasyeyannu namoodiside mattu adannu parishilisalaguttide. "
        "Naavu bega nimmanu samparkisutteve."
    ),
    "Tamil": (
        "Ungal seidhi engalukku vandulladhu 🙏\n\n"
        "Ungal pirachanai pathivu seyyappattulladhu matrum adhai ippo paarththu varugiroam. "
        "Naangal seekiram ungalai thodarpu kolvoam."
    ),
    "Telugu": (
        "Mee sandesham maaku andindi 🙏\n\n"
        "Mee samasya namodayyindi mariyu danini parishilinchtunnamu. "
        "Memu tvaralone mimmalni sampradinchutamu."
    ),
    "Bengali": (
        "Apnar barta peyechi 🙏\n\n"
        "Apnar samasya nôthibhukto kora hoyeche ebong eta porjalochona kora hochhe. "
        "Amra shighroi apnar shathe jogajog korbo."
    ),
    "English": (
        "Thank you for reaching out 🙏\n\n"
        "Your issue has been received and is being reviewed. We will contact you shortly."
    ),
}

_GENERIC_ACK_LATIN: dict[str, str] = {
    "Hindi": (
        "Aapka sandesh mil gaya hai 🙏\n\n"
        "Aapki samasya darj kar li gayi hai aur uski samiksha ho rahi hai. "
        "Hum jald hi aapse sampark karenge."
    ),
    "Hinglish": _GENERIC_ACK["Hinglish"],
    "Marathi": _GENERIC_ACK["Marathi"],
    "Kannada": _GENERIC_ACK["Kannada"],
    "Tamil": _GENERIC_ACK["Tamil"],
    "Telugu": _GENERIC_ACK["Telugu"],
    "Bengali": _GENERIC_ACK["Bengali"],
}

_REVIEW_ACK: dict[str, str] = {
    "Hindi": (
        "Aapka sandesh mil gaya hai 🙏\n\n"
        "Aapka mudda prapt ho gaya hai aur hamari team iski samiksha kar rahi hai. "
        "Hum jald hi aapse sampark karenge."
    ),
    "Hinglish": (
        "Aapka message mil gaya hai 🙏\n\n"
        "Aapka issue receive ho gaya hai aur hamari team uska review kar rahi hai. "
        "Hum aapse jald follow up karenge."
    ),
    "Marathi": (
        "Tumcha sandesh milala aahe 🙏\n\n"
        "Tumcha mudda amhala milala aahe ani aamchi team tyachi tapasani karat aahe. "
        "Amhi lokerach tumchyashi follow up karu."
    ),
    "English": (
        "Thank you for reaching out 🙏\n\n"
        "Your issue has been received and is being reviewed by our team. We will follow up with you shortly."
    ),
}

_REVIEW_ACK_LATIN = _REVIEW_ACK

_UNSUPPORTED_MESSAGE_REPLY: dict[str, str] = {
    "Hindi": (
        "Aapka sandesh mila 🙏\n\n"
        "Humein aapka message mila, lekin hum ise text ke roop mein padh nahi paaye. "
        "Kripya apni samasya type karke text message bhejiye."
    ),
    "Hinglish": (
        "Aapka message mil gaya 🙏\n\n"
        "Humein aapka message mila, but hum ise text ke roop mein read nahi kar paaye. "
        "Please apna issue type karke text message bhejein."
    ),
    "Marathi": (
        "Tumcha sandesh milala 🙏\n\n"
        "Amhala tumcha message milala, pan to text mhanun vachata ala nahi. "
        "Krupaya tumchi samasya type karun text message pathva."
    ),
    "English": (
        "Thank you for reaching out 🙏\n\n"
        "We received your message but couldn’t read it as text. Please type your issue and send it as a text message."
    ),
}

_UNSUPPORTED_MESSAGE_REPLY_LATIN = _UNSUPPORTED_MESSAGE_REPLY

_RATE_LIMIT_REPLY: dict[str, str] = {
    "Hindi": (
        "Aaj aapke number se humein kai sandesh prapt hue hain. "
        "Hamari team inka samiksha karke jald hi aapse sampark karegi. 🙏"
    ),
    "Hinglish": (
        "Aaj aapke number se humein kai messages mile hain. "
        "Hamari team review karke aapse jald sampark karegi. 🙏"
    ),
    "Marathi": (
        "Aaj tumchya number varun amhala anek sandesh milale aahet. "
        "Aamchi team tapasani karun lokerach tumchyashi sampark karel. 🙏"
    ),
    "English": (
        "We've received multiple messages from your number today. Our team will review and follow up. 🙏"
    ),
}

_RATE_LIMIT_REPLY_LATIN = _RATE_LIMIT_REPLY

_LOCATION_UPDATE_ACK: dict[str, str] = {
    "Hindi": (
        "Ji, aapki shikayat *{location}* ke sambandh mein note kar li gayi hai. "
        "Hum aapko jald hi update denge. 🙏"
    ),
    "Hinglish": (
        "Ji, aapka issue *{location}* ke sambandh mein note kar liya gaya hai. "
        "Hum aapko jald update denge. 🙏"
    ),
    "Marathi": (
        "Tumchi *{location}* babatichi samasya nondi keli aahe. "
        "Amhi tumhala lokerach update deu. 🙏"
    ),
    "English": (
        "Your issue regarding *{location}* has been noted. We will update you shortly. 🙏"
    ),
}

_LOCATION_UPDATE_ACK_LATIN = _LOCATION_UPDATE_ACK


# ── Details Request ───────────────────────────────────────────────────────────
# Sent as a SECOND message immediately after the grievance acknowledgment,
# politely asking the citizen for their personal details to help resolve faster.

_DETAILS_REQUEST: dict[str, str] = {
    "Hindi": (
        "Aapki shikayat darz ho gayi hai 🙏\n\n"
        "Aapki madad aur jaldi karne ke liye, kya aap yeh jaankari de sakte hain?\n\n"
        "• *Aapka naam*\n"
        "• *Pata* (ghar ka pata ya gaon/ward)\n"
        "• *Koi khaas jaankari* jo problem samajhne mein madad kare\n\n"
        "Yeh details dene se hum aapki samasya zyada jaldi aur sahi tarike se hal kar payenge. 🙏"
    ),
    "Hinglish": (
        "Aapka issue register ho gaya hai 🙏\n\n"
        "Faster resolution ke liye, please yeh details share karein:\n\n"
        "• *Your name*\n"
        "• *Address* (ghar ka pata ya village/ward)\n"
        "• *Koi specific detail* jo problem explain karne mein help kare\n\n"
        "In details se hum aapka issue aur jaldi resolve kar payenge. 🙏"
    ),
    "Marathi": (
        "तुमची तक्रार नोंदवली गेली आहे 🙏\n\n"
        "तुमची समस्या लवकर सोडवण्यासाठी, कृपया खालील माहिती द्या:\n\n"
        "• *तुमचे नाव*\n"
        "• *पत्ता* (घराचा पत्ता किंवा गाव/वार्ड)\n"
        "• *कोणतीही विशेष माहिती* जी समस्या समजण्यास मदत करेल\n\n"
        "ही माहिती मिळाल्यावर आम्ही तुमची तक्रार अधिक जलद आणि अचूकपणे सोडवू. 🙏"
    ),
    "Kannada": (
        "ನಿಮ್ಮ ದೂರನ್ನು ನೋಂದಾಯಿಸಲಾಗಿದೆ 🙏\n\n"
        "ತ್ವರಿತ ಪರಿಹಾರಕ್ಕಾಗಿ, ದಯವಿಟ್ಟು ಈ ಮಾಹಿತಿ ನೀಡಿ:\n\n"
        "• *ನಿಮ್ಮ ಹೆಸರು*\n"
        "• *ವಿಳಾಸ* (ಮನೆ ವಿಳಾಸ ಅಥವಾ ಗ್ರಾಮ/ವಾರ್ಡ್)\n"
        "• *ಯಾವುದಾದರೂ ನಿರ್ದಿಷ್ಟ ವಿವರ* ಸಮಸ್ಯೆ ಅರ್ಥಮಾಡಿಕೊಳ್ಳಲು ಸಹಾಯ ಮಾಡಲು\n\n"
        "ಈ ವಿವರಗಳಿಂದ ನಾವು ನಿಮ್ಮ ದೂರನ್ನು ಶೀಘ್ರವಾಗಿ ಪರಿಹರಿಸಬಹುದು. 🙏"
    ),
    "Tamil": (
        "உங்கள் புகார் பதிவாகியது 🙏\n\n"
        "விரைவான தீர்வுக்கு, தயவுசெய்து இந்த விவரங்களை தெரிவிக்கவும்:\n\n"
        "• *உங்கள் பெயர்*\n"
        "• *முகவரி* (வீட்டு முகவரி அல்லது கிராமம்/வார்டு)\n"
        "• *எந்த குறிப்பிட்ட விவரமும்* சிக்கலை புரிந்துகொள்ள உதவும்\n\n"
        "இந்த தகவல்கள் மூலம் உங்கள் பிரச்சினையை இன்னும் விரைவாக தீர்க்க முடியும். 🙏"
    ),
    "Telugu": (
        "మీ ఫిర్యాదు నమోదైంది 🙏\n\n"
        "త్వరగా పరిష్కరించడానికి, దయచేసి ఈ వివరాలు అందించండి:\n\n"
        "• *మీ పేరు*\n"
        "• *చిరునామా* (ఇంటి చిరునామా లేదా గ్రామం/వార్డు)\n"
        "• *సమస్యను అర్థం చేసుకోవడానికి ఏదైనా నిర్దిష్ట వివరాలు*\n\n"
        "ఈ సమాచారంతో మేము మీ ఫిర్యాదును మరింత వేగంగా పరిష్కరిస్తాం. 🙏"
    ),
    "Malayalam": (
        "നിങ്ങളുടെ പരാതി രേഖപ്പെടുത്തി 🙏\n\n"
        "വേഗത്തിൽ പരിഹരിക്കാൻ, ദയവായി ഈ വിവരങ്ങൾ നൽകൂ:\n\n"
        "• *നിങ്ങളുടെ പേര്*\n"
        "• *വിലാസം* (വീട്ടു വിലാസം അല്ലെങ്കിൽ ഗ്രാമം/വാർഡ്)\n"
        "• *പ്രശ്‌നം മനസ്സിലാക്കാൻ സഹായിക്കുന്ന ഏതെങ്കിലും നിർദ്ദിഷ്ട വിവരം*\n\n"
        "ഈ വിവരങ്ങൾ ലഭിച്ചാൽ ഞങ്ങൾ നിങ്ങളുടെ പ്രശ്‌നം കൂടുതൽ വേഗം പരിഹരിക്കും. 🙏"
    ),
    "Bengali": (
        "আপনার অভিযোগ নথিভুক্ত হয়েছে 🙏\n\n"
        "দ্রুত সমাধানের জন্য, অনুগ্রহ করে এই তথ্যগুলি জানান:\n\n"
        "• *আপনার নাম*\n"
        "• *ঠিকানা* (বাড়ির ঠিকানা বা গ্রাম/ওয়ার্ড)\n"
        "• *সমস্যা বুঝতে সাহায্য করবে এমন যেকোনো নির্দিষ্ট তথ্য*\n\n"
        "এই তথ্যগুলি পেলে আমরা আপনার সমস্যাটি আরও দ্রুত সমাধান করতে পারব। 🙏"
    ),
    "Gujarati": (
        "તમારી ફરિયાદ નોંધાઈ ગઈ છે 🙏\n\n"
        "ઝડપી સમાધાન માટે, કૃપા કરીને આ માહિતી આપો:\n\n"
        "• *તમારું નામ*\n"
        "• *સરનામું* (ઘરનું સરનામું અથવા ગામ/વોર્ડ)\n"
        "• *સમસ્યા સમજવામાં મદદ કરે તેવી કોઈ ખાસ માહિતી*\n\n"
        "આ વિગતોથી અમે તમારી ફરિયાદ વધુ ઝડપથી ઉકેલી શકીશું. 🙏"
    ),
    "Punjabi": (
        "ਤੁਹਾਡੀ ਸ਼ਿਕਾਇਤ ਦਰਜ ਹੋ ਗਈ ਹੈ 🙏\n\n"
        "ਜਲਦੀ ਹੱਲ ਕੱਢਣ ਲਈ, ਕਿਰਪਾ ਕਰਕੇ ਇਹ ਜਾਣਕਾਰੀ ਦਿਓ:\n\n"
        "• *ਤੁਹਾਡਾ ਨਾਮ*\n"
        "• *ਪਤਾ* (ਘਰ ਦਾ ਪਤਾ ਜਾਂ ਪਿੰਡ/ਵਾਰਡ)\n"
        "• *ਕੋਈ ਖਾਸ ਜਾਣਕਾਰੀ* ਜੋ ਸਮੱਸਿਆ ਸਮਝਣ ਵਿੱਚ ਮਦਦ ਕਰੇ\n\n"
        "ਇਹ ਵੇਰਵੇ ਮਿਲਣ ਨਾਲ ਅਸੀਂ ਤੁਹਾਡੀ ਸਮੱਸਿਆ ਹੋਰ ਜਲਦੀ ਹੱਲ ਕਰ ਸਕਾਂਗੇ। 🙏"
    ),
    "Odia": (
        "ଆପଣଙ୍କ ଅଭିଯୋଗ ଦାଖଲ ହୋଇଛି 🙏\n\n"
        "ଶୀଘ୍ର ସମାଧାନ ପାଇଁ, ଦୟାକରି ଏই ତଥ୍ୟ ଦିଅନ୍ତୁ:\n\n"
        "• *ଆପଣଙ୍କ ନାମ*\n"
        "• *ଠିକଣା* (ଘର ଠିକଣା ବା ଗ୍ରାମ/ୱାର୍ଡ)\n"
        "• *ସମସ୍ୟା ବୁଝିବା ପାଇଁ ଯେ କୌଣସି ନିର୍ଦ୍ଦିଷ୍ଟ ତଥ୍ୟ*\n\n"
        "ଏହି ତଥ୍ୟ ଦ୍ୱାରା ଆମେ ଆପଣଙ୍କ ଅଭିଯୋଗ ଶୀଘ୍ର ସମାଧାନ କରିପାରିବୁ। 🙏"
    ),
    "Assamese": (
        "আপোনাৰ অভিযোগ নথিভুক্ত হৈছে 🙏\n\n"
        "সোনকালে সমাধানৰ বাবে, অনুগ্ৰহ কৰি এই তথ্যসমূহ জনাওক:\n\n"
        "• *আপোনাৰ নাম*\n"
        "• *ঠিকনা* (ঘৰৰ ঠিকনা বা গাঁও/ৱাৰ্ড)\n"
        "• *সমস্যা বুজিবলৈ সহায়ক যিকোনো নিৰ্দিষ্ট তথ্য*\n\n"
        "এই তথ্যসমূহ পালে আমি আপোনাৰ সমস্যাটো অধিক সোনকালে সমাধান কৰিব পাৰিম। 🙏"
    ),
    "Urdu": (
        "آپ کی شکایت درج ہو گئی ہے 🙏\n\n"
        "جلد حل کے لیے، براہ کرم یہ معلومات فراہم کریں:\n\n"
        "• *آپ کا نام*\n"
        "• *پتہ* (گھر کا پتہ یا گاؤں/وارڈ)\n"
        "• *کوئی خاص معلومات* جو مسئلہ سمجھنے میں مدد کرے\n\n"
        "ان تفصیلات سے ہم آپ کی شکایت زیادہ جلدی حل کر سکیں گے۔ 🙏"
    ),
    "English": (
        "Your issue has been registered 🙏\n\n"
        "To help us resolve it quickly, could you please share:\n\n"
        "• *Your name*\n"
        "• *Address* (home address or village/ward)\n"
        "• *Any specific details* that will help us understand the problem better\n\n"
        "Providing these details will help us resolve your issue faster and more accurately. 🙏"
    ),
}

_DEFAULT_DETAILS_REQUEST = _DETAILS_REQUEST["Hindi"]

# Statuses that should receive the follow-up details request
DETAILS_REQUEST_STATUSES = {"incomplete"}


def get_details_request_reply(detected_language: str = "", original_text: str = "") -> str:
    """Return a localized follow-up message asking the citizen for their personal details.

    Sent as a second message after the grievance acknowledgment for valid cases
    (status: new / pending / incomplete).

    Args:
        detected_language: The language tag returned by the AI (e.g. "Marathi").

    Returns:
        A formatted WhatsApp-ready string in the citizen's language.
    """
    return ensure_ji_prefix(_pick_template(_DETAILS_REQUEST, {}, detected_language, original_text) or _DEFAULT_DETAILS_REQUEST)

# Normalize incoming detected_language values to our keys
_LANG_ALIASES: dict[str, str] = {
    "hinglish": "Hinglish",
    "hindi": "Hindi",
    "marathi": "Marathi",
    "tamil": "Tamil",
    "telugu": "Telugu",
    "kannada": "Kannada",
    "malayalam": "Malayalam",
    "bengali": "Bengali",
    "bangla": "Bengali",
    "gujarati": "Gujarati",
    "punjabi": "Punjabi",
    "odia": "Odia",
    "oriya": "Odia",
    "assamese": "Assamese",
    "urdu": "Urdu",
    "english": "English",
}


def get_awaiting_location_reply(location: str, detected_language: str = "", original_text: str = "") -> str:
    """Return a localized 'please clarify your location' message.

    Args:
        location: The unmatched location string the citizen mentioned.
        detected_language: The language tag returned by the AI (e.g. "Marathi").

    Returns:
        A formatted WhatsApp-ready string in the citizen's language.
    """
    template = _pick_template(_AWAITING_LOCATION, _AWAITING_LOCATION_LATIN, detected_language, original_text) or _DEFAULT_AWAITING_LOCATION
    # FIX P1: Use str.replace() instead of .format() to prevent Python format-string
    # injection attacks via crafted location strings (e.g. "{0.__class__.__mro__[1]}").
    # .replace() treats the substitution value as a literal string — no format parsing occurs.
    safe_location = str(location) if location else ""
    return ensure_ji_prefix(template.replace("{location}", safe_location))


_MISSING_LOCATION: dict[str, str] = {
    "Hindi": (
        "Aapka sandesh mil gaya hai 🙏\n\n"
        "Madad ko sahi jagah tak pahunchane ke liye kripya apna area, gaon, ward number ya paas ka landmark bhejiye.\n\n"
        "Jaise hi location milti hai, hum aapki baat turant aage badhayenge."
    ),
    "Hinglish": (
        "Aapka message mil gaya hai 🙏\n\n"
        "Issue ko sahi jagah tak pahunchane ke liye please apna area, village, ward number ya nearest landmark bhej dijiye.\n\n"
        "Location milte hi hum aapki baat turant aage badhayenge."
    ),
    "Marathi": (
        "तुमचा संदेश मिळाला आहे 🙏\n\n"
        "तुमच्या तक्रारीवर योग्य कारवाईसाठी कृपया तुमचा भाग, गाव, वार्ड नंबर किंवा जवळचा landmark पाठवा.\n\n"
        "location मिळताच आम्ही लगेच पुढची कार्यवाही करू."
    ),
    "English": (
        "Thank you for your message 🙏\n\n"
        "To route this issue correctly, please share your area, village, ward number, or nearest landmark.\n\n"
        "As soon as we have the location, we'll move this forward right away."
    ),
}

_MISSING_LOCATION_LATIN: dict[str, str] = {
    "Hindi": (
        "Aapka sandesh mil gaya hai 🙏\n\n"
        "Madad ko sahi jagah tak pahunchane ke liye kripya apna area, gaon, ward number ya paas ka landmark bhejiye.\n\n"
        "Jaise hi location milti hai, hum aapki baat turant aage badhayenge."
    ),
    "Hinglish": _MISSING_LOCATION["Hinglish"],
    "Marathi": (
        "Tumcha sandesh milala aahe 🙏\n\n"
        "Tumchya takrariwar yogya karvayisathi krupaya tumcha bhag, gaav, ward number kiwa javalcha landmark pathva.\n\n"
        "Location miltach amhi lagech pudhchi karvayi karu."
    ),
    "English": _MISSING_LOCATION["English"],
}


def get_missing_location_reply(detected_language: str = "", original_text: str = "") -> str:
    return ensure_ji_prefix(_pick_template(_MISSING_LOCATION, _MISSING_LOCATION_LATIN, detected_language, original_text) or _MISSING_LOCATION["English"])


def get_generic_ack_reply(detected_language: str = "", original_text: str = "") -> str:
    return ensure_ji_prefix(_pick_template(_GENERIC_ACK, _GENERIC_ACK_LATIN, detected_language, original_text) or _GENERIC_ACK["English"])


def get_review_ack_reply(detected_language: str = "", original_text: str = "") -> str:
    return ensure_ji_prefix(_pick_template(_REVIEW_ACK, _REVIEW_ACK_LATIN, detected_language, original_text) or _REVIEW_ACK["English"])


def get_unsupported_message_reply(detected_language: str = "", original_text: str = "") -> str:
    return ensure_ji_prefix(_pick_template(_UNSUPPORTED_MESSAGE_REPLY, _UNSUPPORTED_MESSAGE_REPLY_LATIN, detected_language, original_text) or _UNSUPPORTED_MESSAGE_REPLY["English"])


def get_rate_limit_reply(detected_language: str = "", original_text: str = "") -> str:
    return ensure_ji_prefix(_pick_template(_RATE_LIMIT_REPLY, _RATE_LIMIT_REPLY_LATIN, detected_language, original_text) or _RATE_LIMIT_REPLY["English"])


def get_location_update_reply(location: str, detected_language: str = "", original_text: str = "") -> str:
    template = _pick_template(_LOCATION_UPDATE_ACK, _LOCATION_UPDATE_ACK_LATIN, detected_language, original_text) or _LOCATION_UPDATE_ACK["English"]
    return ensure_ji_prefix(template.replace("{location}", str(location or "")))
