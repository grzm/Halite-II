<?php

include_once "../website/php/WebsiteAPI.php";
include_once "APITest.php";

define("USER_TABLE", "User");
const TEST_USER = array("userID" => "124", "username" => "testUsername");

class UserTest extends APITest { 
	public function testGetUser() {
		$this->insertObject(USER_TABLE, TEST_USER);
		
		// Get with ID			
		$_GET['userID'] = TEST_USER["userID"];
		$_SERVER['REQUEST_METHOD'] = "GET";

    	$returnedUser = json_decode((new WebsiteAPI("user"))->processAPI());
		$this->assertEquals($returnedUser->username, TEST_USER['username']);
		
		// Get with username			
		unset($_GET['userID']);
		$_GET['username'] = TEST_USER['username'];

    	$returnedUser = json_decode((new WebsiteAPI("user"))->processAPI());
		$this->assertEquals($returnedUser->username, TEST_USER['username']);
	}

	public function testActive() {
		$inactiveUser = TEST_USER;
		$this->insertObject(USER_TABLE, $inactiveUser);

		$activeUser = TEST_USER; 
		$activeUser["username"] = "ACTIVE USERNAME";
		$activeUser["userID"] = "478371";
		$this->insertObject(USER_TABLE, $activeUser);
		$activeID = $activeUser['userID'];
		$this->mysqli->query("UPDATE User SET status=3 where userID=$activeID");
		
		$_GET['active'] = 1;
		$_SERVER['REQUEST_METHOD'] = "GET";
    	$returnedUsers = json_decode((new WebsiteAPI("user"))->processAPI());

		$this->assertEquals(count($returnedUsers), 1);	

		$returnedActiveUser = $returnedUsers[0];
		$this->assertEquals($returnedActiveUser->username, $activeUser['username']);
	}
}

?>