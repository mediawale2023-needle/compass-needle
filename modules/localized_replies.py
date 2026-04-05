"""
Localized WhatsApp reply templates for system-generated messages
(i.e. messages NOT written by the AI — used when we override the AI response
for specific flow states like awaiting_location).

Each template receives keyword arguments matching the format() placeholders.
Language keys match the detected_language values returned by ai_engine.py.
"""

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
        "Location confirm hote hi hum aapka complaint forward kar denge. 🙏"
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
        "Once we have the location, we'll make sure your complaint reaches the right team right away."
    ),
}

# Default fallback — covers any language not explicitly listed
_DEFAULT_AWAITING_LOCATION = _AWAITING_LOCATION["Hindi"]

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


def get_awaiting_location_reply(location: str, detected_language: str = "") -> str:
    """Return a localized 'please clarify your location' message.

    Args:
        location: The unmatched location string the citizen mentioned.
        detected_language: The language tag returned by the AI (e.g. "Marathi").

    Returns:
        A formatted WhatsApp-ready string in the citizen's language.
    """
    normalized = _LANG_ALIASES.get((detected_language or "").lower().strip())
    template = _AWAITING_LOCATION.get(normalized, _DEFAULT_AWAITING_LOCATION)
    return template.format(location=location)
