import streamlit as st
import json
import requests
import csv
import pandas as pd

# ------------------------------------------------------
# Package Generator for SourceMember 
# Author: Mohan Chinnappan
# Copyleft software. Maintain the author name in your copies/modifications
# ------------------------------------------------------

class SalesforceQueryTool:
    def __init__(self, auth_data, api_version='60.0', user_did_change=None):
        """
        Initializes the SalesforceQueryTool with necessary parameters.

        :param auth_data: Dictionary containing access_token and instance_url
        :param api_version: Salesforce API version (default is '60.0')
        :param user_did_change: The user who made changes (LastModifiedBy.Name)
        """
        self.access_token = auth_data['access_token']
        self.instance_url = auth_data['instance_url']
        self.api_version = api_version
        self.user_did_change = user_did_change

    def generate_soql(self, member_types=None):
        """
        Generates the SOQL query based on the provided parameters.

        :param member_types: List of selected Member Types (optional)
        :return: The SOQL query string
        """
        query = (
            "SELECT Id, LastModifiedBy.Name, MemberIdOrName, MemberType, MemberName, "
            "RevisionNum, RevisionCounter, IsNameObsolete, LastModifiedById, IsNewMember, ChangedBy "
            "FROM SourceMember "
            "WHERE LastModifiedBy.Name = '{user_did_change}'"
        )
        
        if member_types:
            member_types_list = "', '".join(member_types)
            query += f" AND MemberType IN ('{member_types_list}')"
        
        return query.format(user_did_change=self.user_did_change)

    def run_tooling_query(self, soql_query):
        """
        Executes a SOQL query using Salesforce Tooling API.

        :param soql_query: The SOQL query to execute
        :return: JSON response containing query results
        """
        # Use the API version specified in the instance
        query_url = f"{self.instance_url}/services/data/v{self.api_version}/tooling/query?q={soql_query}"
        
        # Set the headers for the API request
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        # Make the API request
        response = requests.get(query_url, headers=headers)
        
        # Raise an exception if the request fails
        if response.status_code != 200:
            raise Exception(f"Failed to run query: {response.status_code} {response.text}")
        
        return response.json()

    def save_to_csv(self, results, output_csv):
        """
        Saves the query results to a CSV file.

        :param results: JSON response containing query results
        :param output_csv: File path to save the CSV
        """
        if not results['records']:
            st.warning("No records found.")
            return
        
        with open(output_csv, 'w', newline='') as csvfile:
            fieldnames = results['records'][0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for record in results['records']:
                writer.writerow(record)
                
        st.success(f"CSV file saved to {output_csv}")

    def generate_package_xml(self, output_csv, pkg_xml):
        """
        Generates a package.xml file based on the contents of the CSV file.

        :param output_csv: File path of the CSV containing query results
        :param pkg_xml: File path to save the generated package.xml
        """
        members_mapping = {}  # Map MemberType.MemberName to Members
        name_mapping = {}     # Map MemberType to Name

        # Read CSV data and populate mappings
        with open(output_csv, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                member_name = row['MemberName']
                member_type = row['MemberType']

                # Use lists to store multiple mappings for each MemberType or MemberName
                members_mapping.setdefault(f"{member_type}.{member_name}", set()).add(member_name)
                name_mapping.setdefault(member_type, set()).add(member_name)

        # Generate package.xml content
        package_xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
  <version>{self.api_version}</version>
"""
        for member_type, member_names in name_mapping.items():
            package_xml_content += f"""  <types>
"""
            for member_name in member_names:
                member_values = ', '.join(members_mapping.get(f"{member_type}.{member_name}", []))
                package_xml_content += f"""    <members>{member_values}</members>
"""
            package_xml_content += f"""    <name>{member_type}</name>
  </types>
"""

        package_xml_content += """</Package>"""

        # Write the package.xml content to the specified output file
        with open(pkg_xml, 'w') as pkg_file:
            pkg_file.write(package_xml_content)
            
        st.success(f"package.xml saved to {pkg_xml}")

def main():
    """
    Main function to run the Streamlit application.
    """
    st.title( "Pkg Generator for SourceMember" )

    st.sidebar.write("""
    **To get `auth.json`:**
    1. Login into your org using:
       ```bash
       sf force auth web login -r https://login.salesforce.com
       ```
       or for sandboxes:
       ```bash
       sf force auth web login -r https://test.salesforce.com
       ```
       You will receive the username that got logged into this org in the console/terminal.

    2. Run this command to get `auth.json`:
       ```bash
       sf mohanc hello myorg -u username | sed 's/instanceUrl/instance_url/' | sed 's/accessToken/access_token/' auth.json
       ```
    """)

    
    # Upload auth.json file
    auth_json = st.file_uploader("Upload auth.json file", type=['json'])
    
    if auth_json is not None:
        auth_data = json.load(auth_json)
        
        # Input field for API version with a default value of 60.0
        api_version = st.text_input("Salesforce API Version", "60.0")
        
        # Input fields for user-did-change
        user_did_change = st.text_input("User who made changes (LastModifiedBy.Name)")

        # Initialize the tool variable only if auth_data and user_did_change are provided
        tool = None
        
        if user_did_change and api_version:
            tool = SalesforceQueryTool(
                auth_data=auth_data,
                api_version=api_version,
                user_did_change=user_did_change
            )
        
        if st.button("Fetch Member Types"):
            try:
                if tool:
                    # Generate and run the initial SOQL query to fetch member types
                    soql_query = tool.generate_soql()
                    results = tool.run_tooling_query(soql_query)
                    
                    # Extract unique MemberTypes from the results
                    member_types = sorted({record['MemberType'] for record in results['records']})
                    
                    # Store the member_types in session state
                    st.session_state['member_types'] = member_types
                    
                else:
                    st.error("Tool is not initialized. Please check your inputs.")
                
            except Exception as e:
                st.error(f"An error occurred: {e}")
        
        # Load member_types from session state if available
        if 'member_types' in st.session_state:
            selected_member_types = st.multiselect(
                "Select Member Types", 
                st.session_state['member_types'], 
                key='selected_member_types'
            )
            
            # Output file names
            output_csv = st.text_input("Output CSV File Name", "output.csv")
            pkg_xml = st.text_input("Output package.xml File Name", "package.xml")
            
            # Option to display the CSV as a DataFrame
            display_csv = st.checkbox("Display CSV as DataFrame", value=False)
            
            # Option to show the generated SOQL query
            show_soql = st.checkbox("Show Generated SOQL Query", value=False)
            
            if st.button("Run Final Query and Generate Files"):
                try:
                    if tool:
                        # Generate the final SOQL query based on selected Member Types
                        final_query = tool.generate_soql(selected_member_types)
                        
                        # Display the generated SOQL query if the option is selected
                        if show_soql:
                            st.code(final_query, language='sql')
                        
                        # Run the final query and save the results to CSV
                        final_results = tool.run_tooling_query(final_query)
                        tool.save_to_csv(final_results, output_csv)
                        
                        # Generate package.xml from the CSV
                        tool.generate_package_xml(output_csv, pkg_xml)
                        
                        # Display CSV file as DataFrame if selected
                        if display_csv:
                            df = pd.read_csv(output_csv)
                            st.dataframe(df)
                        
                        # Provide download links for the generated files
                        with open(output_csv, "rb") as file:
                            st.download_button(label="Download CSV", data=file, file_name=output_csv, mime='text/csv')
                        
                        with open(pkg_xml, "rb") as file:
                            st.download_button(label="Download package.xml", data=file, file_name=pkg_xml, mime='application/xml')
                        
                    else:
                        st.error("Tool is not initialized. Please check your inputs.")
                
                except Exception as e:
                    st.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()