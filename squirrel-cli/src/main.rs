use dotenv::dotenv;
use std::env;

fn main() {
    dotenv().ok();

    match env::var("SQUIRREL_MONGO_URI") {
        Ok(val) => println!("SQUIRREL_MONGO_URI: {:?}", val),
        Err(e) => panic!("{}", e),
    }
}
