const { ObjectId } = require("mongodb");

async function addWordtoCollection(collection, word) {
  try {
    const document = await collection.findOne(word, { projection: { _id: 1 } });

    if (document) {
      console.log(`Document already exists with ID: ${document._id}`);
      return document._id;
    } else {
      const result = await collection.insertOne(word);
      console.log(`Document inserted with ID: ${result.insertedId}`);
      return result.insertedId;
    }
  } catch (e) {
    throw error;
  }
}

async function addWordtoUser(
  collection,
  wordId,
  userId = "6745c8e0ed379289ace1fc07"
) {
  try {
    const now = new Date().toISOString().split('T')[0];
    const result = await collection.updateOne(
      { _id: ObjectId(userId), "likedWords.wordId": { $ne: wordId } },
      { $addToSet: { likedWords: { wordId: wordId, rep: 1, revAt: now } } }
    );

    if (result.matchedCount === 0) {
      console.log("당신의 목록에 이미 단어가 있습니다.");
      return null;
    }

    if (result.modifiedCount > 0) {
      console.log("성공적으로 당신의 목록에 단어가 추가되었습니다.");
      return true;
    }

  } catch (error) {
    console.error("Error updating likedWords:", error);
    throw error;
  }
}

module.exports = {
  addWordtoCollection,
  addWordtoUser,
};
