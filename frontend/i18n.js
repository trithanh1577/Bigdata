const messages = {
  en: {
    pageTitle: "Recipe Atlas — A world of good food",
    pageDescription: "Explore recipes across cultures, trace their sources, and ask questions grounded in recipe records.",
    skip: "Skip to recipes", brandHome: "Recipe Atlas home", navLabel: "Main navigation",
    navDiscover: "Discover", navAssistant: "Kitchen companion", aboutData: "About the data ↗",
    modeDemo: "Classroom demo", modeApi: "Connected knowledge base", modeError: "Configuration error",
    globalEyebrow: "GLOBAL CULINARY KNOWLEDGE BASE",
    heroTitle: "A little curiosity.<br />A world of <em>flavor.</em>",
    heroDescription: "Find your next favorite dish. Explore recipes across cultures, discover what goes into them, and follow every recipe back to its source.",
    heroButton: "Explore the collection", heroFootnote: "Different traditions. Thoughtful discovery. Sources included.",
    heroImageAlt: "Illustration of a bowl with vegetables and herbs on a warm kitchen table",
    artCaption: "GOOD FOOD HAS A STORY", artNote: "Your next adventure<br /><strong>starts at the table.</strong>",
    artBottom: "THE RECIPE ATLAS COLLECTION / EST. 2026",
    dataBannerStrong: "You're exploring a classroom demo.",
    dataBannerText: "Recipes and answers are synthetic examples, not crawled source material. No medical safety claims.",
    dataBannerApiStrong: "Connected to the recipe knowledge base.",
    dataBannerApiText: "Search and answers use collected recipe records. Source data may be incomplete; ingredient filters cannot guarantee dietary safety.",
    howItWorks: "How it works ↗", discoverEyebrow: "FIND SOMETHING DELICIOUS",
    discoverTitle: "Where shall we eat today?", discoverSubtitle: "A new place. A familiar ingredient.<br />Something worth making.",
    searchLabel: "Search recipes, ingredients, or cuisines", searchPlaceholder: "A dish, an ingredient, a place…",
    searchButton: "Find recipes", filterTitle: "Make it yours", reset: "Reset",
    countryLabel: "Country or region", countryAny: "Anywhere in the world", categoryLabel: "Type of dish", categoryAll: "All categories",
    timeLabel: "Total cooking time", timeAny: "Any duration", time15: "Up to 15 minutes", time30: "Up to 30 minutes", time60: "Up to 1 hour",
    difficultyLabel: "Difficulty", difficultyAny: "Any difficulty", avoidLabel: "Ingredients to avoid",
    avoidPlaceholder: "e.g. peanut, shrimp", avoidHelp: "Separate terms with commas. Matches listed ingredient names, original wording, and declared allergens.",
    requireAllergen: "Only show records with source-declared allergen information",
    allergenCaveat: "Missing allergen data means unknown. Filters cannot check cross-contact or guarantee a dish is safe.",
    applyFilters: "Apply preferences", sidebarTitle: "Every dish has roots.",
    sidebarText: "Open a recipe to see its ingredients, method, and source details.", sortLabel: "Sort by", sortName: "Name A–Z", sortTime: "Quickest first",
    previous: "← Previous", next: "Next →", assistantEyebrow: "A LITTLE HELP IN THE KITCHEN",
    assistantTitle: "Curiosity,<br />meet your companion.",
    assistantIntro: "Ask about ingredients, steps, or recipes that fit your preferences. Answers stay connected to the recipe records they use.",
    assistantNoteDemo: "Demo companion: a local recipe lookup, with no AI model or external service.",
    assistantNoteApi: "Answers use the connected recipe records. Optional model answers use retrieved records. {webSearch}",
    webSearchEnabled: "If a dish is missing, Gemini can search for structured recipe pages and add them with source links.",
    webSearchDisabled: "Automatic web discovery is unavailable until Gemini is configured.",
    assistantNoteApiTranslationUnavailable: "Basic recipe chat works without a model. Configure Gemini in the server-side .env to translate source recipes and automatically search for missing dishes.",
    translationNotice: "Recipe text could not be translated. Check Gemini's connection and quota; the source text is shown.",
    chatTitle: "Kitchen companion", newChat: "New conversation", conversationAria: "Conversation",
    suggestionTomato: "Something with tomato", suggestionJapan: "A taste of Japan", suggestionQuick: "Ready in 30 minutes",
    chatPreferences: "Applied search preferences also apply to new questions.", questionLabel: "Your recipe question",
    questionPlaceholder: "What would you like to cook?", send: "Send question",
    footerTagline: "A world of recipes. A clear view of their sources.", footerProject: "Global Culinary Knowledge Base · Person 4",
    dialogEyebrow: "FROM THE COLLECTION", closeRecipe: "Close recipe", aboutEyebrow: "KNOW YOUR SOURCES",
    closeAbout: "Close data information", aboutTitle: "Good discovery starts with clear data.",
    aboutIntro: "Recipe Atlas is the website component of the Global Culinary Knowledge Base, implemented by Nguyễn Trần Hoàng Nhân (2474802010272).",
    aboutProvenance: "Live recipe records preserve each provider's attribution, source links, license or terms, and collection time. Versions from different providers remain separate. Missing cooking times, difficulty, allergens, nutrition, or substitutions are shown as unavailable, never invented.",
    aboutSafety: "Ingredient exclusion is a text-matching aid. It cannot identify every synonym, hidden ingredient, or cross-contact risk. Missing allergen declarations mean unknown.",
    noscript: "Enable JavaScript to search the recipe collection and use the companion.",
    languageSwitch: "Tiếng Việt", languageSwitchAria: "Switch language to Vietnamese",
    loadingFind: "Finding your next favorite…", loadingTitle: "A moment at the table…", loadingBody: "Loading recipe records.",
    recipeSingular: "recipe", recipePlural: "recipes", demoCollection: "in the demo collection", found: "found",
    emptyTitle: "A different kind of adventure?", emptyBody: "No recipes match all of these preferences. Try a broader search or reset the filters.",
    appliedFilters: "Applied filters", pageOf: "Page {page} of {pages}", collectionUnavailable: "Collection unavailable", collectionErrorTitle: "The collection couldn't load.",
    tryAgain: "Try again", anywhere: "Anywhere in the world", allCategories: "All categories", anyDifficulty: "Any difficulty",
    facetError: "Filter options unavailable.", retryFacets: "Retry filter options", searchChip: "Search: {value}",
    timeChip: "Up to {value} min", avoidChip: "Avoid: {value}", allergensChip: "Allergen declarations available",
    illustrationLabel: "Illustration · not a dish photo", illustrationAlt: "Decorative food illustration; not a photograph of this recipe",
    regionUnknown: "Region not supplied", recipeTeaser: "Open this recipe to explore its ingredients and method.",
    difficultyUnknown: "Difficulty not supplied", sourceLabel: "Source", sourceUnknown: "Not supplied", viewRecipe: "View recipe",
    notSupplied: "Not supplied", descriptionUnknown: "Description not supplied.", originalTitle: "Original title: {value}",
    syntheticNote: "Synthetic classroom example. This is not a crawled source recipe.", servings: "Servings: {value}", servingsUnknown: "Servings not supplied",
    prep: "Prep: {value} min", cook: "Cook: {value} min", ingredients: "Ingredients", ingredientsUnknown: "Ingredients not supplied.",
    makeIt: "Let's make it", instructionsUnknown: "Instructions not supplied.", allergensDiet: "Allergens & dietary information",
    sourceDeclaredAllergens: "Source-declared allergens: {value}.", incomplete: "This list may be incomplete.",
    allergenUnknown: "No source-declared allergen information is available. Allergen status is unknown.",
    crossContact: "Text filters cannot verify dietary suitability or cross-contact risk.", nutritionSource: "Source-declared nutrition",
    nutrition: "Nutrition", nutritionUnknown: "Not supplied by the source.", tools: "Tools", tips: "Source tips",
    substitutions: "Source-declared substitutions", substitutionsUnknown: "No substitutions supplied. The companion will not invent replacements.",
    followSource: "Follow the source", provider: "Provider: {value}", attributionUnknown: "Attribution not supplied.",
    licenseTerms: "License / terms: {value}", licenseLink: "License / terms ↗", collected: "Collected: {value}", sourceUpdated: "Source updated: {value}",
    record: "Record: {value}", providerId: "Provider ID: {value}", providerRecord: "Provider record ↗",
    originalRecipe: "Original recipe ↗", noExternalLinks: "No external source links supplied.", askRecipe: "Ask about this recipe →",
    loadingRecipe: "Loading recipe…", fetchingRecipe: "Fetching the full recipe and source details.", recipeUnavailable: "Recipe unavailable",
    noCitations: "No recipe citations supplied for this response.", citationSource: "Source", chatBusy: "Looking through the recipe records…",
    greetingMock: "Hello, curious cook. I can help you explore this synthetic demo collection. Ask for a dish, an ingredient, or a region; every recipe answer links to its demo records.",
    greetingApi: "Hello, curious cook. Ask about a dish, ingredient, or region. I will display the answer with its recipe citations. Missing source data stays unknown.",
    aboutModeMock: "Demo mode uses eight synthetic classroom recipe records and a deterministic local lookup. It makes no network requests to an API or AI model. Dish illustrations are decorative, not photos of the recipes.",
    aboutModeApi: "API mode searches the configured knowledge base and displays its source records. If the service is unavailable, the interface shows an error and lets you retry. It does not replace real records with demo data.",
    setupRequired: "Setup required", configCheck: "Check the website configuration.",
    apiHttp: "The recipe service returned HTTP {status}. Please try again.", apiTimeout: "The recipe service took too long to respond. Please try again.",
    apiNetwork: "Cannot reach the recipe service. Check its address, availability, and CORS configuration.",
    apiJson: "The recipe service did not return valid JSON.", apiInvalidRecipe: "The API returned an invalid recipe record. Check the frontend API contract.",
    apiInvalidConfig: "Configure apiBaseUrl as an HTTP(S) URL without credentials, a query, or a fragment.",
    apiInvalidMode: "Configuration mode must be \"mock\" or \"api\".", apiInvalidFacets: "The API returned invalid filter options.",
    apiInvalidSearch: "The API returned an invalid search response.", apiMissingRecipe: "That recipe is no longer available.",
    apiInvalidChat: "The API returned an invalid conversation response.", apiInvalidHealth: "The API returned invalid service status.",
  },
  vi: {
    pageTitle: "Recipe Atlas — Khám phá món ngon thế giới",
    pageDescription: "Khám phá công thức nhiều nền ẩm thực, truy nguồn dữ liệu và hỏi đáp dựa trên bản ghi công thức.",
    skip: "Bỏ qua để đến danh sách món", brandHome: "Trang chủ Recipe Atlas", navLabel: "Điều hướng chính",
    navDiscover: "Khám phá", navAssistant: "Trợ lý nhà bếp", aboutData: "Về dữ liệu ↗",
    modeDemo: "Bản minh họa lớp học", modeApi: "Knowledge Base đang kết nối", modeError: "Lỗi cấu hình",
    globalEyebrow: "KHO TRI THỨC ẨM THỰC TOÀN CẦU",
    heroTitle: "Một chút tò mò.<br />Cả thế giới <em>hương vị.</em>",
    heroDescription: "Tìm món ăn yêu thích tiếp theo. Khám phá công thức từ nhiều nền ẩm thực, tìm hiểu nguyên liệu và xem nguồn gốc của từng món.",
    heroButton: "Khám phá bộ sưu tập", heroFootnote: "Đa dạng truyền thống. Khám phá có chọn lọc. Có ghi nguồn.",
    heroImageAlt: "Minh họa tô thức ăn với rau củ và thảo mộc trên bàn bếp ấm cúng",
    artCaption: "MÓN NGON NÀO CŨNG CÓ CÂU CHUYỆN", artNote: "Cuộc khám phá tiếp theo<br /><strong>bắt đầu bên bàn ăn.</strong>",
    artBottom: "BỘ SƯU TẬP RECIPE ATLAS / THÀNH LẬP 2026",
    dataBannerStrong: "Bạn đang xem bản minh họa cho lớp học.",
    dataBannerText: "Công thức và câu trả lời ở đây là dữ liệu mẫu, không phải dữ liệu đã thu thập. Không đưa ra kết luận an toàn y tế.",
    dataBannerApiStrong: "Đang kết nối với Knowledge Base công thức.",
    dataBannerApiText: "Kết quả tìm kiếm và câu trả lời dùng dữ liệu công thức đã thu thập. Dữ liệu nguồn có thể chưa đầy đủ; bộ lọc không đảm bảo an toàn ăn uống.",
    howItWorks: "Cách hoạt động ↗", discoverEyebrow: "TÌM MÓN NGON",
    discoverTitle: "Hôm nay mình ăn gì?", discoverSubtitle: "Một vùng đất mới. Nguyên liệu quen thuộc.<br />Một món đáng để thử.",
    searchLabel: "Tìm công thức, nguyên liệu hoặc nền ẩm thực", searchPlaceholder: "Tên món, nguyên liệu, vùng miền…",
    searchButton: "Tìm món ăn", filterTitle: "Tùy chỉnh món ăn", reset: "Đặt lại",
    countryLabel: "Quốc gia hoặc vùng miền", countryAny: "Mọi nơi trên thế giới", categoryLabel: "Loại món", categoryAll: "Tất cả danh mục",
    timeLabel: "Tổng thời gian nấu", timeAny: "Không giới hạn", time15: "Tối đa 15 phút", time30: "Tối đa 30 phút", time60: "Tối đa 1 giờ",
    difficultyLabel: "Độ khó", difficultyAny: "Mọi mức độ", avoidLabel: "Nguyên liệu cần tránh",
    avoidPlaceholder: "Ví dụ: đậu phộng, tôm", avoidHelp: "Nhập nhiều từ, cách nhau bằng dấu phẩy. Tìm trong tên nguyên liệu, cách ghi gốc và thông tin dị ứng do nguồn cung cấp.",
    requireAllergen: "Chỉ hiện món có thông tin dị ứng do nguồn khai báo",
    allergenCaveat: "Thiếu dữ liệu dị ứng nghĩa là chưa rõ. Bộ lọc không phát hiện nhiễm chéo và không đảm bảo món ăn an toàn.",
    applyFilters: "Áp dụng lựa chọn", sidebarTitle: "Mỗi món ăn đều có nguồn gốc.",
    sidebarText: "Mở công thức để xem nguyên liệu, cách chế biến và thông tin nguồn.", sortLabel: "Sắp xếp theo", sortName: "Tên A–Z", sortTime: "Thời gian nhanh nhất",
    previous: "← Trang trước", next: "Trang sau →", assistantEyebrow: "TRỢ GIÚP MỘT CHÚT TRONG BẾP",
    assistantTitle: "Tò mò một chút,<br />có trợ lý đồng hành.",
    assistantIntro: "Hỏi về nguyên liệu, cách làm hoặc món phù hợp với lựa chọn của bạn. Câu trả lời đi kèm bản ghi công thức làm căn cứ.",
    assistantNoteDemo: "Chế độ minh họa: tra cứu trên dữ liệu mẫu, không dùng mô hình AI hay dịch vụ bên ngoài.",
    assistantNoteApi: "Câu trả lời dựa trên bản ghi công thức đã kết nối. Mô hình chỉ dùng dữ liệu truy xuất được. {webSearch}",
    webSearchEnabled: "Nếu chưa có món, Gemini có thể tìm trang công thức có cấu trúc và lưu kèm liên kết nguồn.",
    webSearchDisabled: "Tự tìm công thức trên web sẽ hoạt động khi đã cấu hình Gemini.",
    assistantNoteApiTranslationUnavailable: "Chat công thức cơ bản vẫn dùng được khi chưa có mô hình. Để dịch công thức nguồn và tự tìm món còn thiếu trên web, hãy cấu hình Gemini trong .env phía máy chủ.",
    translationNotice: "Chưa dịch được nội dung công thức. Hãy kiểm tra kết nối và hạn mức Gemini; hiện đang hiển thị nội dung gốc.",
    chatTitle: "Trợ lý nhà bếp", newChat: "Cuộc trò chuyện mới", conversationAria: "Nội dung trò chuyện",
    suggestionTomato: "Món có cà chua", suggestionJapan: "Hương vị Nhật Bản", suggestionQuick: "Nấu trong 30 phút",
    chatPreferences: "Các bộ lọc đang chọn cũng áp dụng cho câu hỏi mới.", questionLabel: "Câu hỏi về công thức",
    questionPlaceholder: "Bạn muốn nấu món gì?", send: "Gửi câu hỏi",
    footerTagline: "Công thức từ khắp nơi. Nguồn dữ liệu rõ ràng.", footerProject: "Kho tri thức ẩm thực toàn cầu · Người 4",
    dialogEyebrow: "TỪ BỘ SƯU TẬP", closeRecipe: "Đóng công thức", aboutEyebrow: "TÌM HIỂU NGUỒN DỮ LIỆU",
    closeAbout: "Đóng thông tin dữ liệu", aboutTitle: "Khám phá tốt bắt đầu từ dữ liệu rõ ràng.",
    aboutIntro: "Recipe Atlas là giao diện website của Global Culinary Knowledge Base, do Nguyễn Trần Hoàng Nhân (2474802010272) thực hiện.",
    aboutProvenance: "Bản ghi món ăn giữ lại tên nguồn, liên kết, giấy phép hoặc điều khoản và thời điểm thu thập. Bản ghi từ các nguồn khác nhau được giữ riêng. Thông tin còn thiếu như thời gian, độ khó, dị ứng, dinh dưỡng hoặc nguyên liệu thay thế sẽ được ghi là chưa có, không tự suy đoán.",
    aboutSafety: "Bộ lọc nguyên liệu chỉ so khớp văn bản. Nó không nhận diện mọi từ đồng nghĩa, nguyên liệu ẩn hay nguy cơ nhiễm chéo. Thiếu khai báo dị ứng nghĩa là chưa rõ.",
    noscript: "Hãy bật JavaScript để tìm công thức và sử dụng trợ lý.",
    languageSwitch: "English", languageSwitchAria: "Chuyển giao diện sang tiếng Anh",
    loadingFind: "Đang tìm món phù hợp…", loadingTitle: "Đang chuẩn bị…", loadingBody: "Đang tải các bản ghi công thức.",
    recipeSingular: "món", recipePlural: "món", demoCollection: "trong bộ sưu tập minh họa", found: "được tìm thấy",
    emptyTitle: "Thử một hướng khám phá khác nhé?", emptyBody: "Không có món nào phù hợp với tất cả lựa chọn này. Hãy mở rộng tìm kiếm hoặc đặt lại bộ lọc.",
    appliedFilters: "Bộ lọc đang áp dụng", pageOf: "Trang {page}/{pages}", collectionUnavailable: "Không thể tải bộ sưu tập", collectionErrorTitle: "Không tải được dữ liệu món ăn.",
    tryAgain: "Thử lại", anywhere: "Mọi nơi trên thế giới", allCategories: "Tất cả danh mục", anyDifficulty: "Mọi mức độ",
    facetError: "Không tải được lựa chọn bộ lọc.", retryFacets: "Tải lại bộ lọc", searchChip: "Tìm: {value}",
    timeChip: "Tối đa {value} phút", avoidChip: "Tránh: {value}", allergensChip: "Có khai báo dị ứng",
    illustrationLabel: "Hình minh họa · không phải ảnh món ăn", illustrationAlt: "Hình minh họa ẩm thực, không phải ảnh chụp món này",
    regionUnknown: "Nguồn không nêu vùng miền", recipeTeaser: "Mở công thức để xem nguyên liệu và cách chế biến.",
    difficultyUnknown: "Nguồn không nêu độ khó", sourceLabel: "Nguồn", sourceUnknown: "Không có thông tin", viewRecipe: "Xem công thức",
    notSupplied: "Không có thông tin", descriptionUnknown: "Nguồn không cung cấp mô tả.", originalTitle: "Tên gốc: {value}",
    syntheticNote: "Dữ liệu minh họa cho lớp học, không phải công thức đã thu thập từ nguồn.", servings: "Khẩu phần: {value}", servingsUnknown: "Nguồn không nêu khẩu phần",
    prep: "Chuẩn bị: {value} phút", cook: "Nấu: {value} phút", ingredients: "Nguyên liệu", ingredientsUnknown: "Nguồn không cung cấp nguyên liệu.",
    makeIt: "Cách chế biến", instructionsUnknown: "Nguồn không cung cấp hướng dẫn.", allergensDiet: "Dị ứng và thông tin dinh dưỡng",
    sourceDeclaredAllergens: "Chất gây dị ứng do nguồn khai báo: {value}.", incomplete: "Danh sách này có thể chưa đầy đủ.",
    allergenUnknown: "Nguồn không có thông tin chất gây dị ứng. Tình trạng dị ứng chưa rõ.",
    crossContact: "Bộ lọc chữ không thể xác nhận chế độ ăn phù hợp hoặc nguy cơ nhiễm chéo.", nutritionSource: "Dinh dưỡng do nguồn khai báo",
    nutrition: "Dinh dưỡng", nutritionUnknown: "Nguồn không cung cấp thông tin.", tools: "Dụng cụ", tips: "Mẹo từ nguồn",
    substitutions: "Nguyên liệu thay thế do nguồn nêu", substitutionsUnknown: "Nguồn không nêu nguyên liệu thay thế. Trợ lý sẽ không tự đoán.",
    followSource: "Theo dõi nguồn", provider: "Nhà cung cấp: {value}", attributionUnknown: "Nguồn không có thông tin ghi công.",
    licenseTerms: "Giấy phép / điều khoản: {value}", licenseLink: "Giấy phép / điều khoản ↗", collected: "Thu thập lúc: {value}", sourceUpdated: "Nguồn cập nhật: {value}",
    record: "Mã bản ghi: {value}", providerId: "Mã từ nguồn: {value}", providerRecord: "Bản ghi tại nguồn ↗",
    originalRecipe: "Công thức gốc ↗", noExternalLinks: "Nguồn không cung cấp liên kết bên ngoài.", askRecipe: "Hỏi về món này →",
    loadingRecipe: "Đang tải công thức…", fetchingRecipe: "Đang lấy công thức và thông tin nguồn.", recipeUnavailable: "Không tìm thấy công thức",
    noCitations: "Câu trả lời này không có trích dẫn công thức.", citationSource: "Nguồn", chatBusy: "Đang tìm trong các bản ghi công thức…",
    greetingMock: "Chào bạn! Mình có thể giúp khám phá bộ dữ liệu minh họa này. Hãy hỏi về món ăn, nguyên liệu hoặc vùng miền; câu trả lời sẽ liên kết tới bản ghi mẫu.",
    greetingApi: "Chào bạn! Hãy hỏi về món ăn, nguyên liệu hoặc vùng miền. Mình sẽ hiển thị câu trả lời cùng trích dẫn công thức. Dữ liệu nguồn còn thiếu sẽ được ghi là chưa rõ.",
    aboutModeMock: "Chế độ minh họa dùng tám công thức mẫu và tra cứu cục bộ theo quy tắc. Không gọi API hay mô hình AI. Hình món ăn chỉ là minh họa.",
    aboutModeApi: "Chế độ API tìm trong Knowledge Base đã cấu hình và hiển thị bản ghi nguồn. Nếu dịch vụ không hoạt động, website báo lỗi và cho phép thử lại; không tự thay bằng dữ liệu mẫu.",
    setupRequired: "Cần cấu hình", configCheck: "Hãy kiểm tra cấu hình website.",
    apiHttp: "Dịch vụ công thức trả về lỗi HTTP {status}. Vui lòng thử lại.", apiTimeout: "Dịch vụ công thức phản hồi quá lâu. Vui lòng thử lại.",
    apiNetwork: "Không kết nối được dịch vụ công thức. Hãy kiểm tra địa chỉ, trạng thái dịch vụ và cấu hình CORS.",
    apiJson: "Dịch vụ công thức không trả về JSON hợp lệ.", apiInvalidRecipe: "API trả về bản ghi công thức không hợp lệ. Hãy kiểm tra hợp đồng API frontend.",
    apiInvalidConfig: "Hãy đặt apiBaseUrl thành địa chỉ HTTP(S), không kèm thông tin đăng nhập, query hoặc fragment.",
    apiInvalidMode: "Chế độ cấu hình phải là \"mock\" hoặc \"api\".", apiInvalidFacets: "API trả về lựa chọn bộ lọc không hợp lệ.",
    apiInvalidSearch: "API trả về kết quả tìm kiếm không hợp lệ.", apiMissingRecipe: "Công thức này không còn khả dụng.",
    apiInvalidChat: "API trả về phản hồi trò chuyện không hợp lệ.", apiInvalidHealth: "API trả về trạng thái dịch vụ không hợp lệ.",
  },
};

let activeLanguage = "en";

export function initializeLanguage() {
  try {
    const saved = localStorage.getItem("recipe-atlas-language");
    if (saved === "en" || saved === "vi") activeLanguage = saved;
  } catch { /* The site remains usable when browser storage is disabled. */ }
  return activeLanguage;
}

export function currentLanguage() {
  return activeLanguage;
}

export function setLanguage(language) {
  activeLanguage = language === "vi" ? "vi" : "en";
  try { localStorage.setItem("recipe-atlas-language", activeLanguage); } catch { /* Keep the change for this page session. */ }
  return activeLanguage;
}

export function t(key, values = {}, language = activeLanguage) {
  let message = messages[language]?.[key] ?? messages.en[key] ?? key;
  for (const [name, value] of Object.entries(values)) message = message.replaceAll(`{${name}}`, String(value));
  return message;
}

export function applyStaticTranslations(root = document) {
  document.documentElement.lang = activeLanguage;
  document.title = t("pageTitle");
  const description = document.querySelector('meta[name="description"]');
  if (description) description.content = t("pageDescription");
  root.querySelectorAll("[data-i18n]").forEach(node => { node.textContent = t(node.dataset.i18n); });
  root.querySelectorAll("[data-i18n-html]").forEach(node => { node.innerHTML = t(node.dataset.i18nHtml); });
  root.querySelectorAll("[data-i18n-placeholder]").forEach(node => { node.placeholder = t(node.dataset.i18nPlaceholder); });
  root.querySelectorAll("[data-i18n-aria-label]").forEach(node => { node.setAttribute("aria-label", t(node.dataset.i18nAriaLabel)); });
  const languageButton = root.querySelector("#language-toggle");
  if (languageButton) {
    languageButton.textContent = t("languageSwitch");
    languageButton.setAttribute("aria-label", t("languageSwitchAria"));
    languageButton.title = t("languageSwitchAria");
  }
}
