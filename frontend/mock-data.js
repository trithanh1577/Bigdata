// Synthetic teaching fixtures. These are not provider recipes or dietary advice.
const ingredient = (name, quantity, unit = "") => ({ name, original_text: `${quantity} ${unit} ${name}`.replace(/\s+/g, " ").trim(), quantity, unit, notes: "" });

function recipe(id, title, region, categories, minutes, difficulty, ingredients, instructions, description, allergens = []) {
  return {
    schema_version: 1, record_id: `demo-${id}`, title, original_title: title,
    country_or_region: region, image_url: "", original_recipe_url: "", description,
    ingredients, servings: "2", prep_minutes: null, cook_minutes: null,
    total_minutes: minutes, difficulty, tools: [], instructions, tips: [], substitutions: [],
    allergens, nutrition: null, categories, language: "en", source_name: "Classroom demo",
    source_record_id: String(id), source_url: "", source_license: "Synthetic project fixture; not crawled recipe content.",
    source_terms_url: "", attribution: "Recipe Atlas project team — synthetic teaching example.",
    collected_at: "", source_updated_at: "", processed_at: "", content_hash: "",
    duplicate_group_key: `demo-${id}`, metadata: { synthetic: true },
  };
}

export const MOCK_RECIPES = [
  recipe(1, "Tomato & Basil Pasta", "Italy", ["Pasta", "Main course"], 25, "Easy",
    [ingredient("pasta", "180", "g"), ingredient("tomato", "3"), ingredient("basil", "8", "leaves"), ingredient("olive oil", "2", "tbsp"), ingredient("garlic", "2", "cloves")],
    ["Cook the pasta in boiling water according to its packet instructions. Reserve a small cup of the cooking water before draining.", "Chop the tomatoes and garlic. Warm the olive oil in a pan, add the garlic, then add the tomatoes and simmer until softened.", "Toss the pasta with the sauce, loosening with a little cooking water. Tear over the basil and serve."],
    "A bright bowl of tomatoes, torn basil, and pasta. A simple place to start.", ["wheat"]),
  recipe(2, "Ginger Vegetable Rice", "Japan", ["Rice", "Main course"], 30, "Easy",
    [ingredient("rice", "150", "g"), ingredient("carrot", "1"), ingredient("ginger", "1", "tbsp"), ingredient("soy sauce", "1", "tbsp"), ingredient("spring onion", "2")],
    ["Rinse the rice and cook according to the packet directions.", "Finely chop the carrot, ginger, and spring onions. Cook the carrot and ginger in a pan with a little water until tender.", "Fold the vegetables and soy sauce into the cooked rice. Scatter over the spring onions."],
    "Ginger, tender vegetables, and warm rice in a comforting everyday bowl.", ["soy", "wheat"]),
  recipe(3, "Lime & Herb Noodle Salad", "Vietnam", ["Salad", "Noodles"], 20, "Easy",
    [ingredient("rice noodles", "150", "g"), ingredient("cucumber", "1"), ingredient("carrot", "1"), ingredient("lime", "1"), ingredient("mint", "10", "leaves"), ingredient("peanut", "2", "tbsp")],
    ["Prepare the rice noodles following the packet instructions. Drain and rinse in cool water.", "Thinly slice the cucumber and carrot. Pick the mint leaves and squeeze the lime.", "Toss the noodles with the vegetables, mint, and lime juice. Finish with the chopped peanuts."],
    "Cool noodles, crisp vegetables, and a generous squeeze of lime.", ["peanut"]),
  recipe(4, "Chickpea Tomato Stew", "India", ["Stew", "Main course"], 45, "Medium",
    [ingredient("cooked chickpeas", "300", "g"), ingredient("tomato", "3"), ingredient("onion", "1"), ingredient("cumin", "1", "tsp"), ingredient("vegetable oil", "1", "tbsp")],
    ["Chop the onion and tomatoes. Warm the oil in a saucepan and soften the onion.", "Stir in the cumin, then the tomatoes, and cook until the tomatoes begin to break down.", "Add the cooked chickpeas and a little water. Simmer gently until the stew has thickened."],
    "Soft chickpeas and tomatoes, slowly brought together with warm cumin."),
  recipe(5, "Black Bean & Corn Tacos", "Mexico", ["Main course", "Tacos"], 20, "Easy",
    [ingredient("corn tortillas", "4"), ingredient("cooked black beans", "200", "g"), ingredient("sweetcorn", "100", "g"), ingredient("avocado", "1"), ingredient("lime", "1")],
    ["Warm the black beans and sweetcorn together in a small pan with a splash of water.", "Heat the tortillas in a dry pan. Slice the avocado and cut the lime into wedges.", "Fill the tortillas with the bean and corn mixture. Add avocado and serve with lime."],
    "A colorful handful of black beans, sweetcorn, avocado, and lime."),
  recipe(6, "Cucumber Sesame Bowl", "Japan", ["Salad", "Side dish"], 10, "Easy",
    [ingredient("cucumber", "1"), ingredient("sesame seeds", "1", "tbsp"), ingredient("rice vinegar", "1", "tbsp"), ingredient("soy sauce", "1", "tsp")],
    ["Thinly slice the cucumber and place in a bowl.", "Mix the rice vinegar and soy sauce. Toss with the cucumber and sprinkle with sesame seeds."],
    "A crisp, quick side with toasted sesame and a light vinegar dressing.", ["sesame", "soy", "wheat"]),
  recipe(7, "Rustic Vegetable Soup", "Italy", ["Soup", "Main course"], null, "",
    [ingredient("carrot", "2"), ingredient("celery", "2", "stalks"), ingredient("tomato", "2"), ingredient("cooked white beans", "200", "g"), ingredient("water", "600", "ml")],
    ["Dice the carrots, celery, and tomatoes.", "Place the vegetables and water in a saucepan. Simmer until the carrots are tender.", "Add the cooked beans and continue heating until warmed through."],
    "A pot of garden vegetables and white beans. Time and difficulty are not supplied.", ["celery"]),
  recipe(8, "Lemongrass Shrimp Rice", "Vietnam", ["Rice", "Main course"], 35, "Medium",
    [ingredient("shrimp", "200", "g"), ingredient("rice", "150", "g"), ingredient("lemongrass", "1", "stalk"), ingredient("garlic", "1", "clove"), ingredient("vegetable oil", "1", "tbsp")],
    ["Cook the rice according to its packet directions.", "Finely chop the tender part of the lemongrass and the garlic. Warm the oil and gently cook the aromatics.", "Add the shrimp and cook until opaque and cooked through. Serve over the rice."],
    "A warm rice bowl with fragrant lemongrass and shrimp.", ["crustaceans"]),
];
