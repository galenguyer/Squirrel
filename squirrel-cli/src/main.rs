use dotenv::dotenv;
use mongodb::{
    bson::{doc, Document},
    options::CountOptions,
    sync::Client,
};
use serde::{Deserialize, Serialize};

fn main() {
    dotenv().ok();

    let mongo_uri = std::env::var("SQUIRREL_MONGO_URI")
        .expect("Could not find SQUIRREL_MONGO_URI environment variabe");

    let client = Client::with_uri_str(mongo_uri).expect("Couldn't connect to mongo database");
    let database = client.database("dump1090");
    let aircraft = database.collection::<mongodb::bson::Document>("aircraft");
    let doc_count = aircraft.count_documents(doc! {}, CountOptions::builder().build());
    match doc_count {
        Ok(count) => println!("Found {} documents in aircraft database", count),
        Err(e) => println!("Error occured getting document count: {:?}", e),
    }
}
